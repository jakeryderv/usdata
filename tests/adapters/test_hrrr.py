from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from usdata.fetch import ChecksumMismatch
from usdata.protocols import s3
from usdata.providers.base import QueryError
from usdata.providers.noaa.hrrr import BUCKET, Hrrr, HrrrParams, select_runs
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

LIST_URL = f"https://{BUCKET}.s3.amazonaws.com/"
RUN = "hrrr.20240506/conus/hrrr.t20z."
DATA = b"GRIB\x00\x00\x00\x02mock model bytes"


def listing(keys, token=None):
    items = "".join(f"<Contents><Key>{k}</Key><Size>{s}</Size></Contents>" for k, s in keys)
    trunc = (
        f"<IsTruncated>true</IsTruncated><NextContinuationToken>{token}</NextContinuationToken>"
        if token
        else "<IsTruncated>false</IsTruncated>"
    )
    return f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">{trunc}{items}</ListBucketResult>'


def run_listing(variant="wrfsfcf", hours=range(19), size=150_000_000):
    keys = []
    for hour in hours:
        keys.append((f"{RUN}{variant}{hour:02d}.grib2", size + hour))
        keys.append((f"{RUN}{variant}{hour:02d}.grib2.idx", 9000))
    return listing(keys)


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield Hrrr(default_registry().get("noaa:hrrr"), client=client)


def query(**kwargs):
    args: dict[str, Any] = {
        "start": "2024-05-06T20:00Z",
        "end": "2024-05-06T20:00Z",
        "cycle": 20,
        "forecast_hour": 0,
    }
    args.update(kwargs)
    return build_query(**args)


def test_lists_requested_hours_with_sizes_and_valid_times(adapter):
    with respx.mock() as mock:
        route = mock.get(LIST_URL).respond(200, text=run_listing())
        assets = adapter.list_assets(query(forecast_hour="1, 0,1"))
    assert route.call_count == 1
    assert route.calls[0].request.url.params["prefix"] == RUN + "wrfsfcf"
    assert [a.id for a in assets] == [
        "hrrr.20240506.t20z.wrfsfcf01.grib2",
        "hrrr.20240506.t20z.wrfsfcf00.grib2",
    ]
    first = assets[1]
    assert first.href == f"s3://{BUCKET}/{RUN}wrfsfcf00.grib2"
    assert first.size == 150_000_000 and first.media_type == "application/x-grib2"
    assert first.time.start == first.time.end == datetime(2024, 5, 6, 20, tzinfo=UTC)
    assert assets[0].time.start == datetime(2024, 5, 6, 21, tzinfo=UTC)
    assert assets[0].size == 150_000_001


@pytest.mark.parametrize(
    ("file", "variant"),
    [(None, "wrfsfcf"), ("sfc", "wrfsfcf"), ("prs", "wrfprsf"), ("nat", "wrfnatf")],
)
def test_file_variant_selects_prefix(adapter, file, variant):
    params = {} if file is None else {"file": file}
    with respx.mock() as mock:
        route = mock.get(LIST_URL).respond(200, text=run_listing(variant))
        (asset,) = adapter.list_assets(query(**params))
    assert route.calls[0].request.url.params["prefix"] == RUN + variant
    assert asset.id.endswith(f"{variant}00.grib2")


def test_long_cycle_accepts_hour_48_and_lists_paginated(adapter):
    run = "hrrr.20240506/conus/hrrr.t12z.wrfsfcf"
    first = listing([(f"{run}{h:02d}.grib2", 10) for h in range(0, 30)], "next")
    second = listing([(f"{run}{h:02d}.grib2", 10) for h in range(30, 49)])
    with respx.mock() as mock:
        route = mock.get(LIST_URL)
        route.side_effect = [httpx.Response(200, text=first), httpx.Response(200, text=second)]
        assets = adapter.list_assets(
            query(
                start="2024-05-06T12:00Z",
                end="2024-05-06T12:00Z",
                cycle="12",
                forecast_hour=[48, 3],
            )
        )
    assert [a.id[-8:-6] for a in assets] == ["48", "03"]
    assert assets[0].time.start == datetime(2024, 5, 8, 12, tzinfo=UTC)


def test_two_runs_when_the_window_touches_both_days(adapter):
    day1 = listing([("hrrr.20240506/conus/hrrr.t20z.wrfsfcf00.grib2", 1)])
    day2 = listing([("hrrr.20240507/conus/hrrr.t20z.wrfsfcf00.grib2", 2)])
    with respx.mock() as mock:
        route = mock.get(LIST_URL)
        route.side_effect = [httpx.Response(200, text=day1), httpx.Response(200, text=day2)]
        assets = adapter.list_assets(query(start="2024-05-06T20:00Z", end="2024-05-07T20:00Z"))
    assert [a.id for a in assets] == [
        "hrrr.20240506.t20z.wrfsfcf00.grib2",
        "hrrr.20240507.t20z.wrfsfcf00.grib2",
    ]
    assert [call.request.url.params["prefix"] for call in route.calls] == [
        "hrrr.20240506/conus/hrrr.t20z.wrfsfcf",
        "hrrr.20240507/conus/hrrr.t20z.wrfsfcf",
    ]


def test_select_runs_uses_inclusive_bounds():
    start, end = datetime(2024, 5, 6, 3, tzinfo=UTC), datetime(2024, 5, 7, 3, tzinfo=UTC)
    assert select_runs(start, end, 3) == [start, end]
    assert select_runs(start, end, 2) == [datetime(2024, 5, 7, 2, tzinfo=UTC)]
    assert select_runs(start, end, 4) == [datetime(2024, 5, 6, 4, tzinfo=UTC)]
    assert select_runs(start, start, 4) == []


@pytest.mark.parametrize(
    ("raw", "hours"),
    [(5, [5]), ("5,05, 6", [5, 6]), ([0, "18"], [0, 18]), ("1,,2", [1, 2]), ((3,), [3])],
)
def test_forecast_hour_shapes_reach_the_model(adapter, raw, hours):
    params = adapter.parse_params(query(forecast_hour=raw), HrrrParams)
    assert params.forecast_hour == hours
    assert params.cycle == 20 and params.file == "sfc" and params.variant == "wrfsfcf"


@pytest.mark.parametrize("raw", ["", "a", -1, 19, [19], True, 3.5, [], "1,x", {"0": 1}])
def test_forecast_hour_shapes_rejected(adapter, raw):
    with pytest.raises(QueryError, match="forecast_hour"):
        adapter.parse_params(query(forecast_hour=raw), HrrrParams)


def test_missing_run_and_missing_hour_are_named(adapter):
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([]))
        with pytest.raises(
            QueryError, match="no HRRR conus wrfsfcf files for the 2024-05-06 20Z run"
        ):
            adapter.list_assets(query())
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=run_listing(hours=range(3)))
        with pytest.raises(
            QueryError, match="2024-05-06 20Z run has no forecast hour\\(s\\) 05, 07"
        ):
            adapter.list_assets(query(forecast_hour=[1, 5, 7]))


@pytest.mark.parametrize(
    "params",
    [
        {"start": None},
        {"end": None},
        {"cycle": None},
        {"cycle": 24},
        {"cycle": -1},
        {"cycle": "2\uff10"},
        {"cycle": True},
        {"forecast_hour": None},
        {"forecast_hour": 19},
        {"forecast_hour": [0, 19]},
        {"forecast_hour": "0,19"},
        {"forecast_hour": ""},
        {"forecast_hour": 2.5},
        {"file": "subh"},
        {"file": "wrfsfcf"},
        {"file": 1},
        {"channel": 13},
        {"location": "ok"},
        {"variables": ["cape"]},
        {"text": "forecast"},
        {"start": "2014-07-29T00:00", "end": "2014-07-30T12:00", "cycle": 6},
        {"start": "2024-05-06T00:00", "end": "2024-05-07T00:01"},
        {"start": "2024-05-06T21:00Z", "end": "2024-05-06T23:00Z"},
    ],
)
def test_bad_queries_fail_before_network(adapter, params):
    with respx.mock() as mock, pytest.raises(QueryError):
        adapter.list_assets(query(**params))
    assert not mock.calls


def test_subhourly_rejection_names_the_scope(adapter):
    with pytest.raises(QueryError, match="out of scope"):
        adapter.list_assets(query(file="subh"))


def test_hour_48_rejected_for_short_cycle_before_network(adapter):
    with respx.mock() as mock, pytest.raises(QueryError, match="0 to 18"):
        adapter.list_assets(
            query(start="2024-05-06T03:00Z", end="2024-05-06T03:00Z", cycle=3, forecast_hour=48)
        )
    assert not mock.calls


@pytest.mark.l2
def test_manifest_restore_does_not_relist_and_checks_bytes(tmp_path: Path):
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: hrrr-analysis
sources:
  - dataset: noaa:hrrr
    start: 2024-05-06T20:00Z
    end: 2024-05-06T20:00Z
    params: {cycle: 20, forecast_hour: 0}
""")
    key = f"{RUN}wrfsfcf00.grib2"
    with respx.mock() as mock:
        listed = mock.get(LIST_URL).respond(200, text=listing([(key, len(DATA))]))
        downloaded = mock.get(s3.https_url(BUCKET, key)).respond(200, content=DATA)
        first = pull(manifest, root=tmp_path / "cache")
        item = first.fetched[0]
        assert item.provenance.source_url == f"s3://{BUCKET}/{key}"
        assert item.path.read_bytes() == DATA
        assert item.path.name.startswith("hrrr.20240506.t20z.wrfsfcf00")
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
