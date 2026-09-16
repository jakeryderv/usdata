from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from usdata import ChecksumMismatch
from usdata.protocols import s3
from usdata.providers.base import QueryError
from usdata.providers.noaa.glm import GoesGlm
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

PREFIX = "GLM-L2-LCFA/2024/127/20/"
NAME = "OR_GLM-L2-LCFA_G16_s20241272000000_e20241272000200_c20241272000213.nc"
KEY = PREFIX + NAME
LIST_URL = "https://noaa-goes16.s3.amazonaws.com/"
DATA = b"\x89HDF\r\n\x1a\nmock detection bytes"


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
        yield GoesGlm(default_registry().get("noaa:goes-glm"), client=client)


def query(**kwargs):
    args: dict[str, Any] = {
        "start": "2024-05-06T20:00Z",
        "end": "2024-05-06T20:00:30Z",
        "satellite": 16,
    }
    args.update(kwargs)
    return build_query(**args)


def test_listing_paginates_filters_and_preserves_file_metadata(adapter):
    second = KEY.replace("s20241272000000_e20241272000200", "s20241272000200_e20241272000400")
    invalid = [
        KEY.replace("G16", "G18"),
        KEY.replace("GLM-L2-LCFA_", "GLM-L2-LCFA-M6_"),
        KEY + ".json",
        PREFIX + "folder/" + NAME,
        KEY.replace("s20241272000000", "s20249992000000"),
        KEY.replace("e20241272000200", "e20241271959400"),
        KEY.replace("2024/127/20", "2024/127/19"),
        KEY.replace("s20241272000000", "s20241272000400"),
    ]
    with respx.mock() as mock:
        route = mock.get(LIST_URL)
        route.side_effect = [
            httpx.Response(
                200, text=listing([(KEY, 288572), *[(key, 10) for key in invalid]], "next")
            ),
            httpx.Response(200, text=listing([(second, 321340)])),
        ]
        first, next_file = adapter.list_assets(query(satellite="16"))
    assert route.call_count == 2
    assert route.calls[0].request.url.params["prefix"] == PREFIX
    assert route.calls[1].request.url.params["continuation-token"] == "next"
    assert first.id == NAME and first.href == f"s3://noaa-goes16/{KEY}"
    assert first.size == 288572 and first.media_type == "application/x-netcdf"
    assert first.bbox is None and first.checksum is None
    assert first.time.start == datetime(2024, 5, 6, 20, 0, 0, tzinfo=UTC)
    assert first.time.end == datetime(2024, 5, 6, 20, 0, 20, tzinfo=UTC)
    assert next_file.time.start == datetime(2024, 5, 6, 20, 0, 20, tzinfo=UTC)


@pytest.mark.parametrize(
    ("start", "end", "count"),
    [
        ("2024-05-06T20:00:00Z", "2024-05-06T20:00:00Z", 1),
        ("2024-05-06T22:00:00+02:00", "2024-05-06T22:00:00+02:00", 1),
        ("2024-05-06T20:00:00.000001Z", "2024-05-06T20:00:19Z", 0),
        ("2024-05-06T19:59:00Z", "2024-05-06T19:59:59.999999Z", 0),
    ],
)
def test_file_start_selection_is_inclusive_not_overlap(adapter, start, end, count):
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([(KEY, 100)]))
        assert len(adapter.list_assets(query(start=start, end=end))) == count


def test_hours_cross_year_boundary(adapter):
    first = "GLM-L2-LCFA/2023/365/23/" + NAME.replace(
        "s20241272000000_e20241272000200", "s20233652359400_e20240010000000"
    )
    second = "GLM-L2-LCFA/2024/001/00/" + NAME.replace(
        "s20241272000000_e20241272000200", "s20240010000000_e20240010000200"
    )
    with respx.mock() as mock:
        route = mock.get(LIST_URL)
        route.side_effect = [
            httpx.Response(200, text=listing([(first, 10)])),
            httpx.Response(200, text=listing([(second, 11)])),
        ]
        assets = adapter.list_assets(query(start="2023-12-31T23:59Z", end="2024-01-01T00:00:10Z"))
    assert [asset.id for asset in assets] == [first.split("/")[-1], second.split("/")[-1]]
    assert [call.request.url.params["prefix"] for call in route.calls] == [
        "GLM-L2-LCFA/2023/365/23/",
        "GLM-L2-LCFA/2024/001/00/",
    ]


def test_window_starts_at_public_archive(adapter):
    with respx.mock() as mock:
        route = mock.get(LIST_URL).respond(200, text=listing([]))
        assert adapter.list_assets(query(start="2018-02-13T15:00Z", end="2018-02-13T16:20Z")) == []
    assert [call.request.url.params["prefix"] for call in route.calls] == [
        "GLM-L2-LCFA/2018/044/16/"
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"start": None},
        {"end": None},
        {"satellite": None},
        {"satellite": 15},
        {"satellite": 20},
        {"satellite": True},
        {"satellite": []},
        {"satellite": "\uff11\uff16"},
        {"channel": 13},
        {"product": "GLM-L2-LCFA"},
        {"location": "ok"},
        {"variables": ["flash_energy"]},
        {"text": "lightning"},
        {"start": "2018-02-13T15:00", "end": "2018-02-13T16:09"},
        {"start": "2024-05-06T00:00", "end": "2024-05-07T00:01"},
        {"start": "2024-05-06", "end": "2024-05-07"},  # two whole days
    ],
)
def test_bad_queries_fail_before_network(adapter, params):
    with respx.mock() as mock, pytest.raises(QueryError):
        adapter.list_assets(query(**params))
    assert not mock.calls


@pytest.mark.l2
def test_manifest_restore_does_not_relist_and_checks_bytes(tmp_path: Path):
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: glm-file
sources:
  - dataset: noaa:goes-glm
    start: 2024-05-06T20:00Z
    end: 2024-05-06T20:00:10Z
    params: {satellite: 16}
""")
    with respx.mock() as mock:
        listed = mock.get(LIST_URL).respond(200, text=listing([(KEY, len(DATA))]))
        downloaded = mock.get(s3.https_url("noaa-goes16", KEY)).respond(200, content=DATA)
        first = pull(manifest, root=tmp_path / "cache")
        item = first.fetched[0]
        assert item.provenance.source_url == f"s3://noaa-goes16/{KEY}"
        assert item.path.read_bytes() == DATA
        assert pull(manifest, root=tmp_path / "cache").fetched[0].from_cache
        item.path.unlink()
        restored = pull(manifest, root=tmp_path / "cache")
        assert restored.from_lockfile and restored.lockfile == first.lockfile
        assert listed.call_count == 1 and downloaded.call_count == 2
    assert verify(manifest, root=tmp_path / "cache") == []
    item.path.unlink()
    with respx.mock() as mock, pytest.raises(ChecksumMismatch):
        mock.get(s3.https_url("noaa-goes16", KEY)).respond(200, content=b"revised bytes")
        pull(manifest, root=tmp_path / "cache")


def test_one_bare_date_is_one_whole_day(adapter):
    with respx.mock() as mock:
        route = mock.get(LIST_URL).respond(200, text=listing([(KEY, len(DATA))]))
        assets = adapter.list_assets(query(start="2024-05-06", end="2024-05-06"))
    assert [asset.id for asset in assets] == [NAME]
    prefixes = [call.request.url.params["prefix"] for call in route.calls]
    assert len(prefixes) == 24
    assert prefixes[0] == "GLM-L2-LCFA/2024/127/00/" and prefixes[-1] == "GLM-L2-LCFA/2024/127/23/"
