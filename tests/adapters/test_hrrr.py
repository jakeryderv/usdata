from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from usdata import ChecksumMismatch, provenance
from usdata.cache import sha256_bytes, sha256_file
from usdata.manifest import Lockfile, lockfile_path
from usdata.protocols import http, s3
from usdata.providers.base import QueryError
from usdata.providers.noaa.hrrr import BUCKET, Hrrr, HrrrParams, select_runs
from usdata.pull import UpstreamChanged, pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

LIST_URL = f"https://{BUCKET}.s3.amazonaws.com/"
RUN = "hrrr.20240506/conus/hrrr.t20z."
DATA = b"GRIB\x00\x00\x00\x02mock model bytes"
KEY = f"{RUN}wrfsfcf00.grib2"
OBJECT_URL = s3.https_url(BUCKET, KEY)
ETAG = "81198a73ad430c73adfbe3335421ea99"
# Three messages of 40 bytes each; the last runs to the end of the object.
OBJECT = b"".join(b"GRIB" + bytes([number]) * 36 for number in (1, 2, 3))
INDEX = (
    "1:0:d=2024050620:REFC:entire atmosphere:anl:\n"
    "2:40:d=2024050620:TMP:2 m above ground:anl:\n"
    "3:80:d=2024050620:HLCY:3000-0 m above ground:anl:\n"
)
SELECTED = "TMP:2 m above ground,HLCY:3000-0 m above ground"
# Messages 2 and 3 are adjacent, so one GET covers both.
PART = OBJECT[40:120]
PART_ID = "hrrr.20240506.t20z.wrfsfcf00.part-46584c88c62d.grib2"
PART_HREF = f"s3://{BUCKET}/{KEY}#messages=2,3"


def ranged(content: bytes = OBJECT, *, status: int = 206, etag: str = ETAG):
    """Answer a range request the way the bucket does."""

    def respond(request: httpx.Request) -> httpx.Response:
        if request.headers.get("If-Match") != f'"{etag}"':
            return httpx.Response(412)
        start, end = (int(value) for value in request.headers["Range"][6:].split("-"))
        if status == 200:
            return httpx.Response(200, content=content)
        return httpx.Response(
            206,
            content=content[start : end + 1],
            headers={"Content-Range": f"bytes {start}-{end}/{len(content)}"},
        )

    return respond


def arm_partial(mock, *, index: str = INDEX):
    """The listing, HEAD, and index requests one partial listing makes."""
    mock.get(LIST_URL).respond(200, text=listing([(KEY, len(OBJECT))]))
    mock.head(OBJECT_URL).respond(
        200, headers={"Content-Length": str(len(OBJECT)), "ETag": f'"{ETAG}"'}
    )
    return mock.get(f"{OBJECT_URL}.idx").respond(200, text=index)


PARTIAL_MANIFEST = f"""name: hrrr-messages
sources:
  - dataset: noaa:hrrr
    start: 2024-05-06T20:00Z
    end: 2024-05-06T20:00Z
    params: {{cycle: 20, forecast_hour: 0, messages: "{SELECTED}"}}
"""


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
    day = build_query(start="2024-05-07", end="2024-05-07").time
    assert day and day.start and day.end
    assert select_runs(day.start, day.end, 4) == [datetime(2024, 5, 7, 4, tzinfo=UTC)]
    assert select_runs(day.start, day.end, 23) == [datetime(2024, 5, 7, 23, tzinfo=UTC)]


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


def test_messages_resolve_to_one_partial_asset_with_a_stable_identity(adapter) -> None:
    with respx.mock() as mock:
        index = arm_partial(mock)
        (asset,) = adapter.list_assets(query(messages=SELECTED))
        (again,) = adapter.list_assets(query(messages=SELECTED.split(",")))
    assert index.call_count == 2
    assert asset.id == PART_ID == again.id
    assert asset.href == PART_HREF == again.href
    assert asset.size == len(PART) == 80
    assert asset.media_type == "application/x-grib2"
    assert asset.time == again.time and asset.checksum is None


def test_request_order_and_repeats_do_not_change_the_asset(adapter) -> None:
    with respx.mock() as mock:
        arm_partial(mock)
        (first,) = adapter.list_assets(query(messages=SELECTED))
        reversed_order = "HLCY:3000-0 m above ground,TMP:2 m above ground,TMP:2 m above ground"
        (second,) = adapter.list_assets(query(messages=reversed_order))
    assert (first.id, first.href, first.size) == (second.id, second.href, second.size)


def test_a_partial_fetch_concatenates_the_selected_messages(adapter, tmp_path: Path) -> None:
    dest = tmp_path / "part.grib2"
    with respx.mock() as mock:
        arm_partial(mock)
        (asset,) = adapter.list_assets(query(messages=SELECTED))
        route = mock.get(OBJECT_URL)
        route.side_effect = ranged()
        assert adapter.fetch(asset, dest) == dest
    assert dest.read_bytes() == PART
    assert route.call_count == 1
    assert route.calls[0].request.headers["Range"] == "bytes=40-119"
    assert route.calls[0].request.headers["If-Match"] == f'"{ETAG}"'


def test_disjoint_messages_use_one_request_per_run(adapter, tmp_path: Path) -> None:
    dest = tmp_path / "part.grib2"
    with respx.mock() as mock:
        arm_partial(mock)
        (asset,) = adapter.list_assets(
            query(messages="REFC:entire atmosphere,HLCY:3000-0 m above ground")
        )
        route = mock.get(OBJECT_URL)
        route.side_effect = ranged()
        adapter.fetch(asset, dest)
    assert asset.href.endswith("#messages=1,3") and asset.size == 80
    assert [call.request.headers["Range"] for call in route.calls] == ["bytes=0-39", "bytes=80-119"]
    assert dest.read_bytes() == OBJECT[0:40] + OBJECT[80:120]


def test_an_absent_index_never_falls_back_to_the_whole_file(adapter) -> None:
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([(KEY, len(OBJECT))]))
        mock.head(OBJECT_URL).respond(
            200, headers={"Content-Length": str(len(OBJECT)), "ETag": f'"{ETAG}"'}
        )
        absent = mock.get(f"{OBJECT_URL}.idx").respond(404)
        with pytest.raises(QueryError, match="is not published"):
            adapter.list_assets(query(messages=SELECTED))
        assert absent.call_count == 1
        fetched = [c for c in mock.calls if c.request.method == "GET"]
        assert not any(str(call.request.url) == OBJECT_URL for call in fetched)


def test_an_unmatched_selector_names_it_and_lists_the_nearest(adapter) -> None:
    with respx.mock() as mock:
        arm_partial(mock)
        with pytest.raises(QueryError, match="matched no message") as error:
            adapter.list_assets(query(messages="TMPK:2 m above ground"))
    assert "'TMPK:2 m above ground'" in str(error.value)
    assert "TMP" in str(error.value)


@pytest.mark.parametrize("raw", ["", [], "TMP", ":surface", 5, ["TMP:surface", ""]])
def test_bad_message_selectors_fail_before_any_request(adapter, raw) -> None:
    with respx.mock() as mock, pytest.raises(QueryError):
        adapter.list_assets(query(messages=raw))
    assert not mock.calls


def test_fetching_a_partial_asset_this_adapter_never_listed_is_refused(
    adapter, tmp_path: Path
) -> None:
    with respx.mock() as mock:
        arm_partial(mock)
        (asset,) = adapter.list_assets(query(messages=SELECTED))
    with httpx.Client() as other_client:
        other = Hrrr(default_registry().get("noaa:hrrr"), client=other_client)
        with respx.mock() as mock, pytest.raises(QueryError, match="byte ranges"):
            other.fetch(asset, tmp_path / "part.grib2")
        assert not mock.calls


@pytest.mark.l2
def test_partial_provenance_records_the_index_ranges_and_object(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(PARTIAL_MANIFEST)
    with respx.mock() as mock:
        arm_partial(mock)
        mock.get(OBJECT_URL).side_effect = ranged()
        result = pull(manifest, root=tmp_path / "cache")
    (item,) = result.fetched
    record = item.provenance
    assert item.path.name == PART_ID and item.path.read_bytes() == PART
    assert record.source_url == PART_HREF and record.size == 80
    assert record.index_url == f"s3://{BUCKET}/{KEY}.idx"
    assert record.index_checksum == sha256_bytes(INDEX.encode())
    assert [(part.start, part.end) for part in record.ranges] == [(40, 79), (80, 119)]
    # One selector per range, the text the caller wrote where it named one message.
    assert record.selectors == ["TMP:2 m above ground", "HLCY:3000-0 m above ground"]
    assert record.object_size == len(OBJECT) and record.object_etag == ETAG
    assert record.transformations == [f"grib2 messages 2,3 concatenated from s3://{BUCKET}/{KEY}"]
    assert record.is_partial
    assert record.checksum == sha256_file(item.path)
    # The sidecar round-trips, and a whole-file record still parses with no new fields.
    assert provenance.read(item.path) == record


@pytest.mark.l2
def test_restore_reissues_the_pinned_ranges_without_reading_the_index(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(PARTIAL_MANIFEST)
    root = tmp_path / "cache"
    with respx.mock() as mock:
        arm_partial(mock)
        mock.get(OBJECT_URL).side_effect = ranged()
        first = pull(manifest, root=root)
    (item,) = first.fetched
    entry = first.lockfile.assets[0]
    assert entry.asset.id == PART_ID and entry.asset.href == PART_HREF
    assert entry.asset.checksum == entry.provenance.checksum
    item.path.unlink()
    with respx.mock(assert_all_called=False) as mock:
        listed = mock.get(LIST_URL)
        index = mock.get(f"{OBJECT_URL}.idx")
        head = mock.head(OBJECT_URL)
        mock.get(OBJECT_URL).side_effect = ranged()
        restored = pull(manifest, root=root)
    assert restored.from_lockfile and restored.lockfile == first.lockfile
    # The selectors survive the lockfile on disk, and a restore re-records them.
    assert restored.lockfile.assets[0].provenance.selectors == entry.provenance.selectors
    assert restored.fetched[0].provenance.selectors == entry.provenance.selectors
    assert restored.fetched[0].path.read_bytes() == PART
    assert (listed.call_count, index.call_count, head.call_count) == (0, 0, 0)
    assert verify(manifest, root=root) == []
    assert not restored.fetched[0].from_cache
    # A second restore is satisfied by the cache, still without any listing.
    with respx.mock(assert_all_called=False) as mock:
        cached = pull(manifest, root=root)
        assert not mock.calls
    assert cached.fetched[0].from_cache


@pytest.mark.l2
@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"content": OBJECT[:40] + bytes(80)}, UpstreamChanged),
        ({"etag": "republished"}, UpstreamChanged),
        ({"status": 200}, http.RangeNotHonored),
    ],
)
def test_restore_reports_every_way_a_pinned_range_can_fail(tmp_path: Path, kwargs, error) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(PARTIAL_MANIFEST)
    root = tmp_path / "cache"
    with respx.mock() as mock:
        arm_partial(mock)
        mock.get(OBJECT_URL).side_effect = ranged()
        first = pull(manifest, root=root)
    first.fetched[0].path.unlink()
    with respx.mock(assert_all_called=False) as mock:
        index = mock.get(f"{OBJECT_URL}.idx")
        mock.get(OBJECT_URL).side_effect = ranged(**kwargs)
        with pytest.raises(error) as raised:
            pull(manifest, root=root)
        assert index.call_count == 0
    if error is UpstreamChanged:
        assert [drift.asset_id for drift in raised.value.drift] == [PART_ID]
        assert raised.value.drift[0].problem == "upstream changed"
    assert not first.fetched[0].path.exists()
    assert Lockfile.load(lockfile_path(manifest)) == first.lockfile


@pytest.mark.l2
def test_whole_file_listing_and_provenance_are_unchanged_without_messages(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: hrrr-whole
sources:
  - dataset: noaa:hrrr
    start: 2024-05-06T20:00Z
    end: 2024-05-06T20:00Z
    params: {cycle: 20, forecast_hour: 0}
""")
    with respx.mock(assert_all_called=False) as mock:
        mock.get(LIST_URL).respond(200, text=listing([(KEY, len(DATA))]))
        mock.get(OBJECT_URL).respond(200, content=DATA)
        head = mock.head(OBJECT_URL)  # A whole-file listing reads no object metadata.
        (item,) = pull(manifest, root=tmp_path / "cache").fetched
    assert head.call_count == 0
    assert item.asset.id == "hrrr.20240506.t20z.wrfsfcf00.grib2"
    assert item.provenance.transformations == [] and item.provenance.ranges == []
    assert item.provenance.index_url is None and item.provenance.object_etag is None
    assert not item.provenance.is_partial
