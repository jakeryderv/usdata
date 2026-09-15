from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

from usdata.models import Asset, Protocol
from usdata.providers.base import QueryError
from usdata.providers.noaa.nexrad_level3 import (
    ARCHIVE_START,
    BUCKET,
    PRODUCTS,
    NexradLevel3,
    NexradLevel3Params,
    bucket_site,
    product_time,
)
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
        yield NexradLevel3(default_registry().get("noaa:nexrad-level3"), client=client)


def test_key_parsing_and_site_mapping() -> None:
    parsed = product_time("TLX_N0B_2024_05_06_20_02_43")
    assert parsed == ("TLX", "N0B", datetime(2024, 5, 6, 20, 2, 43, tzinfo=UTC))
    assert product_time("TLX_N0B_2024_05_06_20_02") is None
    assert product_time("2024/05/06/KTLX/KTLX20240506_200243_V06") is None
    assert product_time("garbage") is None
    assert bucket_site("KTLX") == "TLX"
    assert bucket_site("pabc") == "ABC"


def test_product_allowlist_covers_tilts_and_single_products() -> None:
    assert {"N0B", "N3B", "NAB", "NBG", "N0Q", "N0U", "N0S", "N0C", "N0X", "N0K", "N0H"} <= set(
        PRODUCTS
    )
    assert {"NCR", "EET", "DVL", "NMD", "NST", "NTV", "NVW", "DAA", "DTA"} <= set(PRODUCTS)
    assert all(len(code) == 3 and code.isupper() for code in PRODUCTS)
    assert all(description for description in PRODUCTS.values())


def codes(adapter: NexradLevel3, **params) -> list[str]:
    """The product codes one query resolves to, through the declared parameter model."""
    query = build_query(site="KTLX", **params)
    return adapter.parse_params(query, NexradLevel3Params).products


def test_product_selection_normalizes_and_validates(adapter: NexradLevel3) -> None:
    assert codes(adapter, products="n0b, nmd,N0B") == ["N0B", "NMD"]
    assert codes(adapter, products=["EET"]) == ["EET"]
    with pytest.raises(QueryError, match="products is required"):
        codes(adapter)
    with pytest.raises(QueryError, match="unknown Level III products: ZZZ"):
        codes(adapter, products="N0B,ZZZ")
    for bad in ("", " , ", []):
        with pytest.raises(QueryError, match="products must not be empty"):
            codes(adapter, products=bad)
    for bad in ([1], 5, None):
        with pytest.raises(QueryError, match="products must be text"):
            codes(adapter, products=bad)
    with pytest.raises(QueryError, match="unsupported"):
        codes(adapter, products="N0B", product="N0B")


def test_the_level_ii_site_rules_carry_into_level_iii(adapter: NexradLevel3) -> None:
    """The model extends its parent's, so the site selection rules come with it."""
    parsed = adapter.parse_params(
        build_query(sites="ktlx, kvnx", products="N0B"), NexradLevel3Params
    )
    assert parsed.sites == ["KTLX", "KVNX"] and parsed.products == ["N0B"]
    with pytest.raises(QueryError, match="pass only one of site or sites"):
        codes(adapter, sites="KVNX", products="N0B")


def test_list_assets_iterates_products_days_and_pages(adapter: NexradLevel3) -> None:
    q = build_query(
        site="KTLX", products="N0B,NMD", start="2024-05-06T23:50", end="2024-05-07T00:20"
    )
    n0b_day1 = listing(
        [("TLX_N0B_2024_05_06_23_45_00", 10), ("TLX_N0B_2024_05_06_23_55_00", 11)], token="tok"
    )
    n0b_day1b = listing([("TLX_N0B_2024_05_06_23_59_00", 12)])
    n0b_day2 = listing([("TLX_N0B_2024_05_07_00_10_00", 13), ("TLX_N0B_2024_05_07_00_30_00", 14)])
    nmd_day1 = listing([("TLX_NMD_2024_05_06_23_55_00", 150)])
    nmd_day2 = listing([])
    with respx.mock() as mock:
        route = mock.get(LIST_URL)
        route.side_effect = [
            httpx.Response(200, text=n0b_day1),
            httpx.Response(200, text=n0b_day1b),
            httpx.Response(200, text=n0b_day2),
            httpx.Response(200, text=nmd_day1),
            httpx.Response(200, text=nmd_day2),
        ]
        assets = adapter.list_assets(q)
    prefixes = [call.request.url.params["prefix"] for call in route.calls]
    assert prefixes == [
        "TLX_N0B_2024_05_06_",
        "TLX_N0B_2024_05_06_",
        "TLX_N0B_2024_05_07_",
        "TLX_NMD_2024_05_06_",
        "TLX_NMD_2024_05_07_",
    ]
    assert route.calls[1].request.url.params["continuation-token"] == "tok"
    assert [a.id for a in assets] == [
        "TLX_N0B_2024_05_06_23_55_00",
        "TLX_N0B_2024_05_06_23_59_00",
        "TLX_N0B_2024_05_07_00_10_00",
        "TLX_NMD_2024_05_06_23_55_00",
    ]
    first = assets[0]
    assert first.size == 11
    assert first.href == f"s3://{BUCKET}/TLX_N0B_2024_05_06_23_55_00"
    assert first.media_type == "application/octet-stream"
    assert first.time is not None
    assert first.time.start == first.time.end == datetime(2024, 5, 6, 23, 55, tzinfo=UTC)


def test_geographic_query_maps_icao_to_bucket_site(adapter: NexradLevel3) -> None:
    q = build_query(
        lat=35.39,
        lon=-97.60,
        radius_km=10,
        products="EET",
        start="2024-05-06T20:00",
        end="2024-05-06T20:05",
    )
    with respx.mock() as mock:
        route = mock.get(LIST_URL).respond(200, text=listing([]))
        assert adapter.list_assets(q) == []
    assert route.calls[0].request.url.params["prefix"] == "TLX_EET_2024_05_06_"


def test_requires_time_window(adapter: NexradLevel3) -> None:
    with pytest.raises(QueryError, match="start and end"):
        adapter.list_assets(build_query(site="KTLX", products="N0B", start="2024-05-06"))


def test_windows_over_31_days_are_rejected_before_listing(adapter: NexradLevel3) -> None:
    q = build_query(site="KTLX", products="N0B", start="2024-05-01", end="2024-06-01T00:01")
    with respx.mock(assert_all_called=False) as mock, pytest.raises(QueryError, match="31 days"):
        adapter.list_assets(q)
    assert not mock.calls


@pytest.mark.parametrize(
    ("start", "end"),
    [("2019-05-06", "2019-05-07"), ("2020-03-29T23:00", "2020-03-30T01:00")],
)
def test_windows_before_the_archive_name_ncei_before_listing(adapter, start, end) -> None:
    q = build_query(site="KTLX", products="N0Q", start=start, end=end)
    with (
        respx.mock(assert_all_called=False) as mock,
        pytest.raises(QueryError, match=r"2020-03-30.*NCEI"),
    ):
        adapter.list_assets(q)
    assert not mock.calls


def test_window_starting_at_the_archive_start_is_listed(adapter: NexradLevel3) -> None:
    q = build_query(site="KTLX", products="NMD", start=ARCHIVE_START, end="2020-03-30T00:05")
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([("TLX_NMD_2020_03_30_00_02_00", 150)]))
        assets = adapter.list_assets(q)
    assert [a.id for a in assets] == ["TLX_NMD_2020_03_30_00_02_00"]


@pytest.mark.parametrize("extra", [{"text": "reflectivity"}, {"variables": ["REF"]}])
def test_unsupported_query_fields_are_rejected_before_listing(adapter, extra) -> None:
    q = build_query(
        site="KTLX", products="N0B", start="2024-05-06T12:00", end="2024-05-06T12:01", **extra
    )
    with respx.mock(assert_all_called=False) as mock, pytest.raises(QueryError, match="support"):
        adapter.list_assets(q)
    assert not mock.calls


def test_missing_products_is_rejected_before_listing(adapter: NexradLevel3) -> None:
    q = build_query(site="KTLX", start="2024-05-06T12:00", end="2024-05-06T12:01")
    with (
        respx.mock(assert_all_called=False) as mock,
        pytest.raises(QueryError, match="products is required: Level III product codes"),
    ):
        adapter.list_assets(q)
    assert not mock.calls


@pytest.mark.l2
def test_fetch_downloads_via_https(tmp_path: Path, adapter: NexradLevel3) -> None:
    asset = Asset(
        id="TLX_EET_2024_05_06_20_02_43",
        dataset_id=adapter.dataset.id,
        href=f"s3://{BUCKET}/TLX_EET_2024_05_06_20_02_43",
        protocol=Protocol.S3,
    )
    with respx.mock() as mock:
        obj = mock.get(f"{LIST_URL}TLX_EET_2024_05_06_20_02_43").mock(
            return_value=httpx.Response(200, content=b"SDUS54 KOUN")
        )
        out = adapter.fetch(asset, tmp_path / "product")
    assert obj.called and out.read_bytes() == b"SDUS54 KOUN"
