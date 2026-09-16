from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from usdata import ChecksumMismatch
from usdata.protocols import s3
from usdata.providers.base import QueryError
from usdata.providers.noaa.gfs import BUCKET, Gfs, forecast_hours
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

LIST_URL = f"https://{BUCKET}.s3.amazonaws.com/"
RUN = "gfs.20240506/00/atmos/gfs.t00z."
DATA = b"GRIB\x00\x00\x00\x02mock model bytes"
KEY = f"{RUN}pgrb2.1p00.f000"
OBJECT_URL = s3.https_url(BUCKET, KEY)
ETAG = "0b331c56f52ef7c459ac80067fc5474c"
OBJECT = b"".join(b"GRIB" + bytes([number]) * 36 for number in (1, 2))
INDEX = "1:0:d=2024050600:PRMSL:mean sea level:anl:\n2:40:d=2024050600:CAPE:surface:anl:\n"
PARTIAL_MANIFEST = """name: gfs-messages
sources:
  - dataset: noaa:gfs
    start: 2024-05-06T00:00Z
    end: 2024-05-06T00:00Z
    params: {cycle: 0, forecast_hour: 0, resolution: 1p00, messages: "CAPE:surface"}
"""


def ranged(content: bytes = OBJECT, *, etag: str = ETAG):
    """Answer a range request the way the bucket does."""

    def respond(request: httpx.Request) -> httpx.Response:
        if request.headers.get("If-Match") != etag:
            return httpx.Response(412)
        start, end = (int(value) for value in request.headers["Range"][6:].split("-"))
        return httpx.Response(
            206,
            content=content[start : end + 1],
            headers={"Content-Range": f"bytes {start}-{end}/{len(content)}"},
        )

    return respond


def arm_partial(mock):
    """The listing, HEAD, and index requests one partial GFS listing makes."""
    mock.get(LIST_URL).respond(200, text=listing([(KEY, len(OBJECT))]))
    mock.head(OBJECT_URL).respond(
        200, headers={"Content-Length": str(len(OBJECT)), "ETag": f'"{ETAG}"'}
    )
    return mock.get(f"{OBJECT_URL}.idx").respond(200, text=INDEX)


def listing(keys, token=None):
    items = "".join(f"<Contents><Key>{k}</Key><Size>{s}</Size></Contents>" for k, s in keys)
    trunc = (
        f"<IsTruncated>true</IsTruncated><NextContinuationToken>{token}</NextContinuationToken>"
        if token
        else "<IsTruncated>false</IsTruncated>"
    )
    return f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">{trunc}{items}</ListBucketResult>'


def run_listing(resolution="0p25", hours=None, size=500_000_000):
    """One run's ``pgrb2`` files with their ``.idx`` sidecars, as the bucket lists them."""
    keys = []
    for hour in forecast_hours(resolution) if hours is None else hours:
        keys.append((f"{RUN}pgrb2.{resolution}.f{hour:03d}", size + hour))
        keys.append((f"{RUN}pgrb2.{resolution}.f{hour:03d}.idx", 9000))
    return listing(keys)


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield Gfs(default_registry().get("noaa:gfs"), client=client)


def query(**kwargs):
    args: dict[str, Any] = {
        "start": "2024-05-06T00:00Z",
        "end": "2024-05-06T00:00Z",
        "cycle": 0,
        "forecast_hour": 0,
    }
    args.update(kwargs)
    return build_query(**args)


def test_forecast_hours_follow_each_resolution_schedule():
    quarter = forecast_hours("0p25")
    assert quarter[:3] == [0, 1, 2] and quarter[119:124] == [119, 120, 123, 126, 129]
    assert quarter[-1] == 384 and len(quarter) == 209
    for resolution in ("0p50", "1p00"):
        coarse = forecast_hours(resolution)
        assert coarse == list(range(0, 385, 3)) and len(coarse) == 129


def test_lists_requested_hours_with_sizes_and_valid_times(adapter):
    with respx.mock() as mock:
        route = mock.get(LIST_URL).respond(200, text=run_listing())
        assets = adapter.list_assets(query(forecast_hour="3, 0,3"))
    assert route.call_count == 1
    assert route.calls[0].request.url.params["prefix"] == RUN + "pgrb2.0p25.f"
    assert [a.id for a in assets] == [
        "gfs.20240506.t00z.pgrb2.0p25.f003",
        "gfs.20240506.t00z.pgrb2.0p25.f000",
    ]
    first = assets[1]
    assert first.href == f"s3://{BUCKET}/{RUN}pgrb2.0p25.f000"
    assert first.size == 500_000_000 and first.media_type == "application/x-grib2"
    assert first.time.start == first.time.end == datetime(2024, 5, 6, 0, tzinfo=UTC)
    assert assets[0].time.start == datetime(2024, 5, 6, 3, tzinfo=UTC)
    assert assets[0].size == 500_000_003


@pytest.mark.parametrize("resolution", [None, "0p25", "0p50", "1p00"])
def test_resolution_selects_prefix(adapter, resolution):
    params = {} if resolution is None else {"resolution": resolution}
    expected = resolution or "0p25"
    with respx.mock() as mock:
        route = mock.get(LIST_URL).respond(200, text=run_listing(expected, hours=[0]))
        (asset,) = adapter.list_assets(query(**params))
    assert route.calls[0].request.url.params["prefix"] == f"{RUN}pgrb2.{expected}.f"
    assert asset.id == f"gfs.20240506.t00z.pgrb2.{expected}.f000"


def test_three_hourly_hour_384_and_paginated_listing(adapter):
    run = "gfs.20240506/12/atmos/gfs.t12z.pgrb2.1p00.f"
    hours = forecast_hours("1p00")
    first = listing([(f"{run}{h:03d}", 10) for h in hours[:70]], "next")
    second = listing([(f"{run}{h:03d}", 10) for h in hours[70:]])
    with respx.mock() as mock:
        route = mock.get(LIST_URL)
        route.side_effect = [httpx.Response(200, text=first), httpx.Response(200, text=second)]
        assets = adapter.list_assets(
            query(
                start="2024-05-06T12:00Z",
                end="2024-05-06T12:00Z",
                cycle="12",
                forecast_hour=[384, 3],
                resolution="1p00",
            )
        )
    assert [a.id[-3:] for a in assets] == ["384", "003"]
    assert assets[0].time.start == datetime(2024, 5, 22, 12, tzinfo=UTC)


def test_two_runs_when_the_window_touches_both_days(adapter):
    day1 = listing([("gfs.20240506/18/atmos/gfs.t18z.pgrb2.0p25.f000", 1)])
    day2 = listing([("gfs.20240507/18/atmos/gfs.t18z.pgrb2.0p25.f000", 2)])
    with respx.mock() as mock:
        route = mock.get(LIST_URL)
        route.side_effect = [httpx.Response(200, text=day1), httpx.Response(200, text=day2)]
        assets = adapter.list_assets(
            query(start="2024-05-06T18:00Z", end="2024-05-07T18:00Z", cycle=18)
        )
    assert [a.id for a in assets] == [
        "gfs.20240506.t18z.pgrb2.0p25.f000",
        "gfs.20240507.t18z.pgrb2.0p25.f000",
    ]
    assert [call.request.url.params["prefix"] for call in route.calls] == [
        "gfs.20240506/18/atmos/gfs.t18z.pgrb2.0p25.f",
        "gfs.20240507/18/atmos/gfs.t18z.pgrb2.0p25.f",
    ]


def test_listing_ignores_sidecars_analysis_and_other_families(adapter):
    keys = [
        (f"{RUN}pgrb2.0p25.f000", 1),
        (f"{RUN}pgrb2.0p25.f000.idx", 2),
        (f"{RUN}pgrb2.0p25.anl", 3),
        (f"{RUN}pgrb2b.0p25.f000", 4),
        (f"{RUN}pgrb2full.0p50.f000", 5),
    ]
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing(keys))
        (asset,) = adapter.list_assets(query())
    assert asset.href.endswith("pgrb2.0p25.f000") and asset.size == 1


def test_missing_run_and_missing_hour_are_named(adapter):
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([]))
        with pytest.raises(QueryError, match="no GFS pgrb2 0p25 files for the 2024-05-06 00Z run"):
            adapter.list_assets(query())
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=run_listing(hours=range(3)))
        with pytest.raises(
            QueryError, match="2024-05-06 00Z run has no forecast hour\\(s\\) 005, 007"
        ):
            adapter.list_assets(query(forecast_hour=[1, 5, 7]))


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"cycle": 3}, "cycle must be 0, 6, 12, or 18"),
        ({"cycle": 20}, "cycle must be 0, 6, 12, or 18"),
        ({"forecast_hour": 121}, "121 are not published at 0p25: files are hourly to 120"),
        ({"forecast_hour": [0, 122, 125]}, "122, 125 are not published at 0p25"),
        (
            {"forecast_hour": 1, "resolution": "1p00"},
            "001 are not published at 1p00: files are every 3 hours",
        ),
        ({"forecast_hour": "0,2", "resolution": "0p50"}, "002 are not published at 0p50"),
    ],
)
def test_cycle_and_hour_schedule_rejections_name_the_rule(adapter, params, message):
    with respx.mock() as mock, pytest.raises(QueryError, match=message):
        adapter.list_assets(query(**params))
    assert not mock.calls


@pytest.mark.parametrize(
    "params",
    [
        {"start": None},
        {"end": None},
        {"cycle": None},
        {"cycle": 24},
        {"cycle": -1},
        {"cycle": "\uff10\uff16"},
        {"cycle": True},
        {"forecast_hour": None},
        {"forecast_hour": 385},
        {"forecast_hour": [0, 387]},
        {"forecast_hour": "0,385"},
        {"forecast_hour": ""},
        {"forecast_hour": 2.5},
        {"resolution": "0p125"},
        {"resolution": "0P25"},
        {"resolution": 1},
        {"file": "sfc"},
        {"location": "ok"},
        {"variables": ["cape"]},
        {"text": "forecast"},
        {"start": "2021-03-21T00:00", "end": "2021-03-22T06:00", "cycle": 6},
        {"start": "2024-05-06T00:00", "end": "2024-05-07T00:01"},
        {"start": "2024-05-06T01:00Z", "end": "2024-05-06T05:00Z"},
    ],
)
def test_bad_queries_fail_before_network(adapter, params):
    with respx.mock() as mock, pytest.raises(QueryError):
        adapter.list_assets(query(**params))
    assert not mock.calls


def test_hrrr_file_variant_is_not_a_gfs_parameter(adapter):
    with pytest.raises(QueryError, match="file"):
        adapter.list_assets(query(file="prs"))


@pytest.mark.l2
def test_manifest_restore_does_not_relist_and_checks_bytes(tmp_path: Path):
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: gfs-analysis
sources:
  - dataset: noaa:gfs
    start: 2024-05-06T00:00Z
    end: 2024-05-06T00:00Z
    params: {cycle: 0, forecast_hour: 0, resolution: 1p00}
""")
    key = f"{RUN}pgrb2.1p00.f000"
    with respx.mock() as mock:
        listed = mock.get(LIST_URL).respond(200, text=listing([(key, len(DATA))]))
        downloaded = mock.get(s3.https_url(BUCKET, key)).respond(200, content=DATA)
        first = pull(manifest, root=tmp_path / "cache")
        item = first.fetched[0]
        assert item.provenance.source_url == f"s3://{BUCKET}/{key}"
        assert item.path.read_bytes() == DATA
        assert item.path.name.startswith("gfs.20240506.t00z.pgrb2.1p00.f000")
        assert pull(manifest, root=tmp_path / "cache").fetched[0].from_cache
        item.path.unlink()
        restored = pull(manifest, root=tmp_path / "cache")
        assert restored.from_lockfile and restored.lockfile == first.lockfile
        assert listed.call_count == 1 and downloaded.call_count == 2
    assert verify(manifest, root=tmp_path / "cache") == []
    item.path.unlink()
    with respx.mock() as mock, pytest.raises(ChecksumMismatch):
        mock.get(s3.https_url(BUCKET, key)).respond(200, content=b"revised bytes")
        pull(manifest, root=tmp_path / "cache")


def test_a_partial_gfs_id_appends_the_digest_because_keys_carry_no_extension(adapter) -> None:
    with respx.mock() as mock:
        arm_partial(mock)
        (asset,) = adapter.list_assets(query(resolution="1p00", messages="CAPE:surface"))
        (again,) = adapter.list_assets(query(resolution="1p00", messages=["CAPE:surface"]))
    assert asset.id == "gfs.20240506.t00z.pgrb2.1p00.f000.part-d4735e3a265e"
    assert asset.id == again.id and asset.href == again.href
    assert asset.href == f"s3://{BUCKET}/{KEY}#messages=2"
    assert asset.size == 40 and asset.media_type == "application/x-grib2"


def test_the_index_sidecar_is_the_key_plus_idx(adapter) -> None:
    with respx.mock() as mock:
        index = arm_partial(mock)
        adapter.list_assets(query(resolution="1p00", messages="CAPE:surface"))
    assert str(index.calls[0].request.url).endswith("gfs.t00z.pgrb2.1p00.f000.idx")


@pytest.mark.l2
def test_gfs_messages_round_trip_through_a_lockfile(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(PARTIAL_MANIFEST)
    root = tmp_path / "cache"
    with respx.mock() as mock:
        arm_partial(mock)
        mock.get(OBJECT_URL).side_effect = ranged()
        first = pull(manifest, root=root)
    (item,) = first.fetched
    assert item.path.read_bytes() == OBJECT[40:80]
    assert item.provenance.object_etag == ETAG and item.provenance.object_size == len(OBJECT)
    assert [(part.start, part.end) for part in item.provenance.ranges] == [(40, 79)]
    item.path.unlink()
    with respx.mock(assert_all_called=False) as mock:
        listed = mock.get(LIST_URL)
        index = mock.get(f"{OBJECT_URL}.idx")
        mock.get(OBJECT_URL).side_effect = ranged()
        restored = pull(manifest, root=root)
    assert restored.from_lockfile and restored.lockfile == first.lockfile
    assert restored.fetched[0].path.read_bytes() == OBJECT[40:80]
    assert listed.call_count == 0 and index.call_count == 0
    assert verify(manifest, root=root) == []
