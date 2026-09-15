from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from usdata.fetch import ChecksumMismatch
from usdata.protocols import s3
from usdata.providers.base import QueryError
from usdata.providers.noaa.mrms import PRODUCTS, Mrms, file_time
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

PRODUCT = "RotationTrackML30min_00.50"
PREFIX = f"CONUS/{PRODUCT}/20240506/"
NAME = f"MRMS_{PRODUCT}_20240506-200000.grib2.gz"
KEY = PREFIX + NAME
LIST_URL = "https://noaa-mrms-pds.s3.amazonaws.com/"
DATA = b"\x1f\x8b\x08\x00mock gzipped grib2 bytes"


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
        yield Mrms(default_registry().get("noaa:mrms"), client=client)


def query(**kwargs):
    args: dict[str, Any] = {
        "start": "2024-05-06T20:00Z",
        "end": "2024-05-06T20:01Z",
        "product": PRODUCT,
    }
    args.update(kwargs)
    return build_query(**args)


def test_listing_paginates_filters_and_preserves_file_metadata(adapter):
    second = KEY.replace("-200000", "-200200")
    invalid = [
        KEY.replace(PRODUCT + "_2024", "RotationTrack30min_00.50_2024"),
        KEY.replace(".grib2.gz", ".grib2"),
        KEY + ".idx",
        PREFIX + "folder/" + NAME,
        KEY.replace("20240506-200000", "20240506-206000"),
        KEY.replace("20240506-200000", "20240506-195959"),
        KEY.replace("20240506-200000", "20240506-200201"),
        "CONUS/MESH_00.50/20240506/" + NAME,
    ]
    with respx.mock() as mock:
        route = mock.get(LIST_URL)
        route.side_effect = [
            httpx.Response(
                200, text=listing([(KEY, 95201), *[(key, 10) for key in invalid]], "next")
            ),
            httpx.Response(200, text=listing([(second, 96304)])),
        ]
        first, next_file = adapter.list_assets(query(end="2024-05-06T20:02Z"))
    assert route.call_count == 2
    assert route.calls[0].request.url.params["prefix"] == PREFIX
    assert route.calls[1].request.url.params["continuation-token"] == "next"
    assert first.id == NAME and first.href == f"s3://noaa-mrms-pds/{KEY}"
    assert first.size == 95201 and first.media_type == "application/x-grib2"
    assert first.bbox is None and first.checksum is None
    assert first.time.start == first.time.end == datetime(2024, 5, 6, 20, 0, tzinfo=UTC)
    assert next_file.time.start == datetime(2024, 5, 6, 20, 2, tzinfo=UTC)


@pytest.mark.parametrize(
    ("start", "end", "count"),
    [
        ("2024-05-06T20:00:00Z", "2024-05-06T20:00:00Z", 1),
        ("2024-05-06T22:00:00+02:00", "2024-05-06T22:00:00+02:00", 1),
        ("2024-05-06T20:00:00.000001Z", "2024-05-06T20:01:59Z", 0),
        ("2024-05-06T19:59:00Z", "2024-05-06T19:59:59.999999Z", 0),
    ],
)
def test_file_stamp_selection_is_inclusive(adapter, start, end, count):
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([(KEY, 100)]))
        assert len(adapter.list_assets(query(start=start, end=end))) == count


def test_stamps_with_seconds_are_kept_exactly(adapter):
    name = "MRMS_MESH_00.50_20240506-200039.grib2.gz"
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([("CONUS/MESH_00.50/20240506/" + name, 5)]))
        (asset,) = adapter.list_assets(query(product="MESH_00.50", end="2024-05-06T20:00:39Z"))
    assert asset.id == name
    assert asset.time.start == datetime(2024, 5, 6, 20, 0, 39, tzinfo=UTC)


def test_days_cross_midnight_and_month_boundary(adapter):
    first = "CONUS/RotationTrackML30min_00.50/20240430/" + NAME.replace(
        "20240506-200000", "20240430-235800"
    )
    second = "CONUS/RotationTrackML30min_00.50/20240501/" + NAME.replace(
        "20240506-200000", "20240501-000000"
    )
    with respx.mock() as mock:
        route = mock.get(LIST_URL)
        route.side_effect = [
            httpx.Response(200, text=listing([(first, 10)])),
            httpx.Response(200, text=listing([(second, 11)])),
        ]
        assets = adapter.list_assets(query(start="2024-04-30T23:58Z", end="2024-05-01T00:00Z"))
    assert [asset.id for asset in assets] == [first.split("/")[-1], second.split("/")[-1]]
    assert [call.request.url.params["prefix"] for call in route.calls] == [
        "CONUS/RotationTrackML30min_00.50/20240430/",
        "CONUS/RotationTrackML30min_00.50/20240501/",
    ]


def test_window_starts_at_public_archive(adapter):
    with respx.mock() as mock:
        route = mock.get(LIST_URL).respond(200, text=listing([]))
        assert adapter.list_assets(query(start="2020-10-13T12:00Z", end="2020-10-14T00:10Z")) == []
    assert [call.request.url.params["prefix"] for call in route.calls] == [
        "CONUS/RotationTrackML30min_00.50/20201014/"
    ]


def test_windows_ending_before_the_archive_are_rejected_before_listing(adapter):
    with respx.mock() as mock, pytest.raises(QueryError, match="archive begins on 2020-10-14"):
        adapter.list_assets(query(start="2020-10-13T12:00Z", end="2020-10-13T23:59Z"))
    assert not mock.calls


@pytest.mark.parametrize(
    "params",
    [
        {"start": None},
        {"end": None},
        {"product": None},
        {"product": ""},
        {"product": 7},
        {"product": ["MESH_00.50"]},
        {"product": "rotationtrackml30min_00.50"},
        {"product": "RotationTrackML30min"},
        {"product": "ProbSevere"},
        {"domain": "ALASKA"},
        {"location": "ok"},
        {"variables": ["reflectivity"]},
        {"text": "rotation"},
        {"start": "2020-10-01", "end": "2020-10-13"},
        {"start": "2024-05-06T00:00", "end": "2024-05-07T00:01"},
    ],
)
def test_bad_queries_fail_before_network(adapter, params):
    with respx.mock() as mock, pytest.raises(QueryError):
        adapter.list_assets(query(**params))
    assert not mock.calls


def test_near_miss_product_names_are_suggested(adapter):
    with respx.mock(), pytest.raises(QueryError, match=r"did you mean MESH_00\.50"):
        adapter.list_assets(query(product="mesh_00.50"))
    with respx.mock(), pytest.raises(QueryError, match="supported products are"):
        adapter.list_assets(query(product="nope"))


def test_every_supported_product_has_a_description():
    assert len(PRODUCTS) >= 20
    assert all(name.strip() == name and meaning for name, meaning in PRODUCTS.items())


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (NAME, (PRODUCT, datetime(2024, 5, 6, 20, 0, tzinfo=UTC))),
        (
            "MRMS_MESH_00.50_20240506-200039.grib2.gz",
            ("MESH_00.50", datetime(2024, 5, 6, 20, 0, 39, tzinfo=UTC)),
        ),
        ("MRMS_MESH_00.50_20240506-200039.grib2", None),
        ("MRMS_MESH_00.50_20240506-246000.grib2.gz", None),
        ("MRMS_MESH_00.50_20240230-000000.grib2.gz", None),
        ("MESH_00.50_20240506-200039.grib2.gz", None),
    ],
)
def test_file_time_parses_stamps_and_rejects_other_objects(name, expected):
    assert file_time(name) == expected


@pytest.mark.l2
def test_manifest_restore_does_not_relist_and_checks_bytes(tmp_path: Path):
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(f"""name: mrms-file
sources:
  - dataset: noaa:mrms
    start: 2024-05-06T20:00Z
    end: 2024-05-06T20:00Z
    params: {{product: {PRODUCT}}}
""")
    with respx.mock() as mock:
        listed = mock.get(LIST_URL).respond(200, text=listing([(KEY, len(DATA))]))
        downloaded = mock.get(s3.https_url("noaa-mrms-pds", KEY)).respond(200, content=DATA)
        first = pull(manifest, root=tmp_path / "cache")
        item = first.fetched[0]
        assert item.provenance.source_url == f"s3://noaa-mrms-pds/{KEY}"
        assert item.path.read_bytes() == DATA
        assert item.path.name.endswith(".grib2.gz")
        assert pull(manifest, root=tmp_path / "cache").fetched[0].from_cache
        item.path.unlink()
        restored = pull(manifest, root=tmp_path / "cache")
        assert restored.from_lockfile and restored.lockfile == first.lockfile
        assert listed.call_count == 1 and downloaded.call_count == 2
    assert verify(manifest, root=tmp_path / "cache") == []
    item.path.unlink()
    with respx.mock() as mock, pytest.raises(ChecksumMismatch):
        mock.get(s3.https_url("noaa-mrms-pds", KEY)).respond(200, content=b"revised bytes")
        pull(manifest, root=tmp_path / "cache")
