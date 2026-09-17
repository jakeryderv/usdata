"""NBM adapter: regions named after the hour, the open hour range, listing, and partial fetch."""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx

from usdata.protocols import s3
from usdata.providers.base import QueryError
from usdata.providers.noaa.nbm import BUCKET, REGIONS, Nbm
from usdata.query import build_query
from usdata.registry import default_registry

LIST_URL = f"https://{BUCKET}.s3.amazonaws.com/"
RUN = "blend.20240506/20/core/blend.t20z.core."
KEY = f"{RUN}f001.co.grib2"
OBJECT_URL = s3.https_url(BUCKET, KEY)
ETAG = "6648f068b20b83071fbfb0bf15aafeb6"
OBJECT = b"".join(b"GRIB" + bytes([number]) * 36 for number in (1, 2))
INDEX = (
    "1:0:d=2024050620:APTMP:2 m above ground:1 hour fcst:\n"
    "2:40:d=2024050620:TMP:2 m above ground:1 hour fcst:\n"
)


def listing(keys):
    items = "".join(f"<Contents><Key>{k}</Key><Size>{s}</Size></Contents>" for k, s in keys)
    return (
        '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        f"<IsTruncated>false</IsTruncated>{items}</ListBucketResult>"
    )


def run_listing(hours: Iterable[int] = range(1, 37), regions=REGIONS, size=170_000_000):
    """Every region's files interleaved, as the shared core prefix lists them."""
    keys = []
    for hour in hours:
        for region in regions:
            keys.append((f"{RUN}f{hour:03d}.{region}.grib2", size + hour))
            keys.append((f"{RUN}f{hour:03d}.{region}.grib2.idx", 20000))
    return listing(keys)


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield Nbm(default_registry().get("noaa:nbm"), client=client)


def query(**kwargs):
    args: dict[str, Any] = {
        "start": "2024-05-06T20:00Z",
        "end": "2024-05-06T20:00Z",
        "cycle": 20,
        "forecast_hour": 1,
    }
    args.update(kwargs)
    return build_query(**args)


def test_lists_one_region_from_the_shared_prefix_with_valid_times(adapter):
    with respx.mock() as mock:
        route = mock.get(LIST_URL).respond(200, text=run_listing())
        assets = adapter.list_assets(query(forecast_hour="3,1"))
    assert route.call_count == 1
    assert route.calls[0].request.url.params["prefix"] == RUN + "f"
    assert [a.id for a in assets] == [
        "blend.20240506.t20z.core.f003.co.grib2",
        "blend.20240506.t20z.core.f001.co.grib2",
    ]
    first = assets[1]
    assert first.href == f"s3://{BUCKET}/{KEY}" and first.size == 170_000_001
    assert first.time and first.time.start == datetime(2024, 5, 6, 21, tzinfo=UTC)
    assert assets[0].time and assets[0].time.start == datetime(2024, 5, 6, 23, tzinfo=UTC)


@pytest.mark.parametrize("region", list(REGIONS))
def test_region_selects_its_files_and_ignores_the_others(adapter, region):
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=run_listing(hours=[1]))
        (asset,) = adapter.list_assets(query(region=region))
    assert asset.id == f"blend.20240506.t20z.core.f001.{region}.grib2"
    assert asset.href.endswith(f"f001.{region}.grib2")


def test_an_hour_the_run_does_not_publish_is_named_after_the_listing(adapter):
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=run_listing(hours=[1, 2, 3, 6]))
        with pytest.raises(QueryError, match="2024-05-06 20Z run has no forecast hour\\(s\\) 004"):
            adapter.list_assets(query(forecast_hour=[1, 4]))
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([]))
        with pytest.raises(QueryError, match="no NBM core co files for the 2024-05-06 20Z run"):
            adapter.list_assets(query())


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"forecast_hour": 0}, "forecast_hour must be an integer from 1 to 264"),
        ({"forecast_hour": 265}, "forecast_hour must be an integer from 1 to 264"),
        ({"region": "conus"}, "region must be co, ak, hi, pr, or gu"),
        ({"file": "sfc"}, "unsupported noaa:nbm params: file"),
    ],
)
def test_rejections_name_the_rule(adapter, params, message):
    with respx.mock() as mock, pytest.raises(QueryError, match=message):
        adapter.list_assets(query(**params))
    assert not mock.calls


@pytest.mark.parametrize(
    "params",
    [
        {"start": None},
        {"cycle": None},
        {"cycle": 24},
        {"forecast_hour": None},
        {"location": "ok"},
        {"variables": ["2t"]},
        {"text": "forecast"},
        {"start": "2020-09-29T00:00", "end": "2020-09-29T06:00", "cycle": 6},
        {"start": "2024-05-06T00:00", "end": "2024-05-07T00:01"},
        {"start": "2024-05-06T01:00Z", "end": "2024-05-06T05:00Z"},
    ],
)
def test_bad_queries_fail_before_network(adapter, params):
    with respx.mock() as mock, pytest.raises(QueryError):
        adapter.list_assets(query(**params))
    assert not mock.calls


def test_messages_resolve_to_one_partial_asset(adapter) -> None:
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([(KEY, len(OBJECT))]))
        mock.head(OBJECT_URL).respond(
            200, headers={"Content-Length": str(len(OBJECT)), "ETag": f'"{ETAG}"'}
        )
        index = mock.get(f"{OBJECT_URL}.idx").respond(200, text=INDEX)
        (asset,) = adapter.list_assets(query(messages="TMP:2 m above ground"))
    assert str(index.calls[0].request.url).endswith("f001.co.grib2.idx")
    assert asset.id == "blend.20240506.t20z.core.f001.co.part-d4735e3a265e.grib2"
    assert asset.href == f"s3://{BUCKET}/{KEY}#messages=2" and asset.size == 40
