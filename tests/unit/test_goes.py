from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from usdata.fetch import ChecksumMismatch
from usdata.protocols import s3
from usdata.providers.base import QueryError
from usdata.providers.noaa.goes import GoesAbi
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

PREFIX = "ABI-L2-CMIPC/2024/127/12/"
NAME = "OR_ABI-L2-CMIPC-M6C06_G18_s20241271201181_e20241271203560_c20241271204021.nc"
KEY = PREFIX + NAME
LIST_URL = "https://noaa-goes18.s3.amazonaws.com/"
DATA = b"\x89HDF\r\n\x1a\nmock scene bytes"


def listing(keys, token=None):
    items = "".join(f"<Contents><Key>{k}</Key><Size>{s}</Size></Contents>" for k, s in keys)
    trunc = (
        f"<IsTruncated>true</IsTruncated><NextContinuationToken>{token}</NextContinuationToken>"
        if token
        else "<IsTruncated>false</IsTruncated>"
    )
    return f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">{trunc}{items}</ListBucketResult>'


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield GoesAbi(default_registry().get("noaa:goes-abi"), client=client)


def query(**kwargs):
    args: dict[str, Any] = {
        "start": "2024-05-06T12:00Z",
        "end": "2024-05-06T12:05Z",
        "satellite": 18,
        "channel": 6,
    }
    args.update(kwargs)
    return build_query(**args)


def test_listing_paginates_filters_and_preserves_scene_metadata(adapter):
    invalid = [
        KEY.replace("C06", "C13"),
        KEY.replace("G18", "G16"),
        KEY.replace("CMIPC", "CMIPF"),
        KEY + ".json",
        PREFIX + "folder/" + NAME,
        KEY.replace("s20241271201181", "s20249991201181"),
        KEY.replace("e20241271203560", "e20241271200180"),
        KEY.replace("2024/127/12", "2024/127/11"),
        KEY.replace("s20241271201181", "s20241271206181"),
    ]
    with respx.mock() as mock:
        route = mock.get(LIST_URL)
        route.side_effect = [
            httpx.Response(
                200, text=listing([(KEY, 255384), *[(key, 10) for key in invalid]], "next")
            ),
            httpx.Response(200, text=listing([(KEY, 255384)])),
        ]
        (asset,) = adapter.list_assets(query(channel="C06", satellite="18"))
    assert route.call_count == 2
    assert route.calls[0].request.url.params["prefix"] == PREFIX
    assert route.calls[1].request.url.params["continuation-token"] == "next"
    assert asset.id == NAME and asset.href == f"s3://noaa-goes18/{KEY}"
    assert asset.size == 255384 and asset.media_type == "application/x-netcdf"
    assert asset.bbox is None and asset.checksum is None
    assert asset.time.start == datetime(2024, 5, 6, 12, 1, 18, 100000, tzinfo=UTC)
    assert asset.time.end == datetime(2024, 5, 6, 12, 3, 56, tzinfo=UTC)


@pytest.mark.parametrize(
    ("start", "end", "count"),
    [
        ("2024-05-06T12:01:18.1Z", "2024-05-06T12:01:18.1Z", 1),
        ("2024-05-06T14:01:18.1+02:00", "2024-05-06T14:01:18.1+02:00", 1),
        ("2024-05-06T12:01:18.100001Z", "2024-05-06T12:03:00Z", 0),
        ("2024-05-06T12:00:00Z", "2024-05-06T12:01:18.099999Z", 0),
    ],
)
def test_scan_start_selection_is_inclusive_not_overlap(adapter, start, end, count):
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([(KEY, 100)]))
        assert len(adapter.list_assets(query(start=start, end=end))) == count


def test_hours_cross_year_and_all_scan_modes(adapter):
    first = "ABI-L2-CMIPC/2023/365/23/" + NAME.replace("M6", "M3").replace(
        "20241271201181", "20233652359181"
    ).replace("20241271203560", "20240010001560")
    second = "ABI-L2-CMIPC/2024/001/00/" + NAME.replace("M6", "M4").replace(
        "20241271201181", "20240010001181"
    ).replace("20241271203560", "20240010003560")
    with respx.mock() as mock:
        route = mock.get(LIST_URL)
        route.side_effect = [
            httpx.Response(200, text=listing([(first, 10)])),
            httpx.Response(200, text=listing([(second, 11)])),
        ]
        assets = adapter.list_assets(query(start="2023-12-31T23:59Z", end="2024-01-01T00:02Z"))
    assert len(assets) == 2
    assert [call.request.url.params["prefix"] for call in route.calls] == [
        "ABI-L2-CMIPC/2023/365/23/",
        "ABI-L2-CMIPC/2024/001/00/",
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"start": None},
        {"end": None},
        {"channel": None},
        {"satellite": None},
        {"satellite": 15},
        {"satellite": 20},
        {"satellite": True},
        {"satellite": []},
        {"channel": True},
        {"channel": 1.0},
        {"channel": ""},
        {"channel": "C17"},
        {"channel": 0},
        {"channel": "foo"},
        {"channel": [6]},
        {"channel": "\uff11"},
        {"product": "ABI-L2-CMIPF"},
        {"channels": "6,13"},
        {"location": "ok"},
        {"variables": ["CMI"]},
        {"text": "clouds"},
        {"start": "2000-01-01T12:00", "end": "2000-01-01T12:05"},
    ],
)
def test_bad_queries_fail_before_network(adapter, params):
    with respx.mock() as mock, pytest.raises(QueryError):
        adapter.list_assets(query(**params))
    assert not mock.calls


def test_reject_non_leap_day_366(adapter):
    key = KEY.replace("2024/127", "2023/365").replace("2024127", "2023366")
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([(key, 100)]))
        assert adapter.list_assets(query(start="2023-12-31T12:00", end="2023-12-31T12:05")) == []


def test_manifest_restore_does_not_relist_and_checks_bytes(tmp_path: Path):
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: goes-scene
sources:
  - dataset: noaa:goes-abi
    start: 2024-05-06T12:00Z
    end: 2024-05-06T12:05Z
    params: {satellite: 18, channel: 6}
""")
    with respx.mock() as mock:
        listed = mock.get(LIST_URL).respond(200, text=listing([(KEY, len(DATA))]))
        downloaded = mock.get(s3.https_url("noaa-goes18", KEY)).respond(200, content=DATA)
        first = pull(manifest, root=tmp_path / "cache")
        item = first.fetched[0]
        assert item.provenance.source_url == f"s3://noaa-goes18/{KEY}"
        assert item.path.read_bytes() == DATA
        assert pull(manifest, root=tmp_path / "cache").fetched[0].from_cache
        item.path.unlink()
        restored = pull(manifest, root=tmp_path / "cache")
        assert restored.from_lockfile and restored.lockfile == first.lockfile
        assert listed.call_count == 1 and downloaded.call_count == 2
    assert verify(manifest, root=tmp_path / "cache") == []
    item.path.unlink()
    with respx.mock() as mock, pytest.raises(ChecksumMismatch):
        mock.get(s3.https_url("noaa-goes18", KEY)).respond(200, content=b"revised bytes")
        pull(manifest, root=tmp_path / "cache")


def test_client_ownership(monkeypatch):
    dataset = default_registry().get("noaa:goes-abi")
    owned = httpx.Client()
    monkeypatch.setattr("usdata.providers.noaa.goes.http.client", lambda: owned)
    with GoesAbi(dataset) as adapter, respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([]))
        assert adapter.list_assets(query()) == []
    assert owned.is_closed
    with httpx.Client() as injected:
        with GoesAbi(dataset, client=injected):
            pass
        assert not injected.is_closed
