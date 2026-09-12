import time
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import respx

from usdata.models import BBox, Query, TimeRange
from usdata.providers.base import QueryError
from usdata.providers.noaa import sites
from usdata.providers.noaa.nexrad import BUCKET, NexradLevel2, scan_time
from usdata.query import build_query
from usdata.registry import default_registry

LIST_URL = f"https://{BUCKET}.s3.amazonaws.com/"
NS = "http://s3.amazonaws.com/doc/2006-03-01/"


def listing(keys: list[tuple[str, int]], token: str | None = None) -> str:
    items = "".join(
        f"<Contents><Key>{k}</Key><ETag>&quot;abc&quot;</ETag><Size>{n}</Size></Contents>"
        for k, n in keys
    )
    trunc = (
        f"<IsTruncated>true</IsTruncated><NextContinuationToken>{token}</NextContinuationToken>"
        if token
        else "<IsTruncated>false</IsTruncated>"
    )
    return f'<?xml version="1.0"?><ListBucketResult xmlns="{NS}">{trunc}{items}</ListBucketResult>'


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield NexradLevel2(default_registry().get("noaa:nexrad-level2"), client=client)


def test_scan_time_parses_all_key_generations() -> None:
    t = datetime(2024, 5, 6, 20, 2, 43, tzinfo=UTC)
    assert scan_time("2024/05/06/KTLX/KTLX20240506_200243_V06") == t
    assert scan_time("KTLX20240506_200243_V03.gz") == t
    assert scan_time("KTLX20240506_200243.gz") == t
    assert scan_time("KTLX20240506_200243_V06_MDM") is None
    assert scan_time("garbage") is None


def test_site_table_and_geometry() -> None:
    ktlx = sites.get_site("ktlx")
    assert ktlx.state == "OK" and ktlx.type == "NEXRAD"
    assert ktlx.distance_km(35.39, -97.60) < 40
    assert sites.nearest(35.39, -97.60)[0].id == "KTLX"
    ok = BBox(west=-103.0, south=33.6, east=-94.4, north=37.0)
    inside = sites.sites_in(ok)
    assert {s.id for s in inside} >= {"KTLX", "KVNX", "KFDR", "KINX"}
    assert all(s.type == "NEXRAD" for s in inside)
    with pytest.raises(KeyError):
        sites.get_site("XXXX")


def test_site_selection_rules(adapter: NexradLevel2) -> None:
    assert adapter.select_sites(build_query(site="ktlx")) == ["KTLX"]
    assert adapter.select_sites(build_query(sites="KTLX, KVNX")) == ["KTLX", "KVNX"]
    ok = build_query(location="ok").bbox
    assert ok is not None
    assert adapter.select_sites(build_query(location="ok")) == [s.id for s in sites.sites_in(ok)]
    # A small box with no radar inside falls back to the nearest one.
    assert adapter.select_sites(build_query(lat=35.39, lon=-97.60, radius_km=10)) == ["KTLX"]
    assert len(adapter.select_sites(build_query(lat=35.39, lon=-97.60, nearest=3))) == 3
    with pytest.raises(QueryError):
        adapter.select_sites(build_query())
    with pytest.raises(QueryError):
        adapter.select_sites(build_query(site="XXXX"))


def test_list_assets_spans_days_filters_window_and_paginates(adapter: NexradLevel2) -> None:
    q = build_query(site="KTLX", start="2024-05-06T23:50", end="2024-05-07T00:20")
    d1, d2 = "2024/05/06/KTLX/", "2024/05/07/KTLX/"
    day1 = listing(
        [(d1 + "KTLX20240506_234500_V06", 10), (d1 + "KTLX20240506_235500_V06", 11)], token="tok"
    )
    day1b = listing([(d1 + "KTLX20240506_235500_V06_MDM", 1)])
    day2 = listing([(d2 + "KTLX20240507_001000_V06", 12), (d2 + "KTLX20240507_003000_V06", 13)])
    with respx.mock() as mock:
        route = mock.get(LIST_URL)
        route.side_effect = [
            httpx.Response(200, text=day1),
            httpx.Response(200, text=day1b),
            httpx.Response(200, text=day2),
        ]
        assets = adapter.list_assets(q)
    assert route.call_count == 3
    assert route.calls[0].request.url.params["prefix"] == "2024/05/06/KTLX/"
    assert route.calls[1].request.url.params["continuation-token"] == "tok"
    assert route.calls[2].request.url.params["prefix"] == "2024/05/07/KTLX/"
    assert [a.id for a in assets] == ["KTLX20240506_235500_V06", "KTLX20240507_001000_V06"]
    first = assets[0]
    assert first.size == 11
    assert first.href == f"s3://{BUCKET}/{d1}KTLX20240506_235500_V06"
    assert first.time is not None
    assert first.time.start == datetime(2024, 5, 6, 23, 55, tzinfo=UTC)


def test_requires_time_window(adapter: NexradLevel2) -> None:
    with pytest.raises(QueryError, match="start and end"):
        adapter.list_assets(build_query(site="KTLX", start="2024-05-06"))


def test_windows_over_31_days_are_rejected_before_listing(adapter: NexradLevel2) -> None:
    q = build_query(site="KTLX", start="2024-05-01", end="2024-06-01T00:01")
    with respx.mock(assert_all_called=False) as mock, pytest.raises(QueryError, match="31 days"):
        adapter.list_assets(q)
    assert not mock.calls


@pytest.mark.parametrize("extra", [{"text": "reflectivity"}, {"variables": ["REF"]}])
def test_unsupported_query_fields_are_rejected_before_listing(adapter, extra) -> None:
    q = build_query(site="KTLX", start="2024-05-06T12:00", end="2024-05-06T12:01", **extra)
    with respx.mock(assert_all_called=False) as mock, pytest.raises(QueryError, match="support"):
        adapter.list_assets(q)
    assert not mock.calls


@pytest.mark.l2
def test_fetch_downloads_via_https(tmp_path: Path, adapter: NexradLevel2) -> None:
    from usdata.models import Asset, Protocol

    asset = Asset(
        id="KTLX20240506_235500_V06",
        dataset_id=adapter.dataset.id,
        href=f"s3://{BUCKET}/2024/05/06/KTLX/KTLX20240506_235500_V06",
        protocol=Protocol.S3,
    )
    with respx.mock() as mock:
        obj = mock.get(f"{LIST_URL}2024/05/06/KTLX/KTLX20240506_235500_V06").mock(
            return_value=httpx.Response(200, content=b"AR2V0006.")
        )
        out = adapter.fetch(asset, tmp_path / "scan")
    assert obj.called and out.read_bytes() == b"AR2V0006."


@pytest.mark.parametrize(
    "params",
    [
        {"site": "KTLX", "nearestt": 2},
        {"site": "KTLX", "sites": "KVNX"},
        {"site": "KTLX", "nearest": 2},
        {"sites": ""},
        {"sites": None},
        {"sites": [123]},
        {"sites": 123},
        {"nearest": 0},
        {"nearest": -1},
        {"nearest": 1.5},
        {"nearest": True},
        {"nearest": "two"},
    ],
)
def test_rejects_invalid_provider_params(adapter: NexradLevel2, params: dict) -> None:
    with pytest.raises(QueryError):
        adapter.select_sites(build_query(location="ok", **params))


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="requires process timezone control")
@pytest.mark.parametrize("offset", [None, -5])
def test_direct_query_uses_utc_independently_of_local_timezone(adapter, monkeypatch, offset):
    start = datetime(
        2024,
        5,
        6,
        12 if offset is None else 7,
        tzinfo=None if offset is None else timezone(timedelta(hours=offset)),
    )
    query = Query(
        time=TimeRange(start=start, end=start + timedelta(minutes=1)), params={"site": "KTLX"}
    )
    keys = [(f"2024/05/06/KTLX/KTLX20240506_{hour}0000_V06", 10) for hour in ("12", "17")]
    try:
        with monkeypatch.context() as environment:
            environment.setenv("TZ", "EST5")
            time.tzset()
            with respx.mock() as mock:
                mock.get(LIST_URL).respond(200, text=listing(keys))
                assets = adapter.list_assets(query)
                normalized = adapter.list_assets(
                    build_query(start="2024-05-06T12:00", end="2024-05-06T12:01", site="KTLX")
                )
    finally:
        time.tzset()
    assert [asset.id for asset in assets] == ["KTLX20240506_120000_V06"]
    assert assets == normalized
    assert query.time is not None and query.time.start == start
