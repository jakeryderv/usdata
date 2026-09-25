"""ComCat adapter: bounds validation, the count-then-page listing, and the CSV fetch path."""

from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata import build_query, fetch, get
from usdata.cli import app
from usdata.models import Query
from usdata.providers.base import QueryError
from usdata.providers.usgs.earthquakes import (
    COUNT_URL,
    QUERY_URL,
    Earthquakes,
    EarthquakesParams,
)

CSV = (
    b"time,latitude,longitude,depth,mag,magType,nst,gap,dmin,rms,net,id,updated,place,type,"
    b"horizontalError,depthError,magError,magNst,status,locationSource,magSource\n"
    b"2024-05-06T00:56:19.550Z,35.54233333,-96.7505,6.05,1.4,ml,96,44,0.0126,0.18,ok,ok2024iwhg,"
    b'2024-11-19T17:58:22.315Z,"8 km NW of Prague, Oklahoma",earthquake,,0.2,0.29,40,'
    b"reviewed,ok,ok\n"
)


def adapter() -> Earthquakes:
    return Earthquakes(get("usgs:earthquakes"))


def query(**kwargs):
    return build_query(**{"start": "2024-05-06", "end": "2024-05-07", **kwargs})


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start": None, "end": None},
        {"end": None},
        {"text": "quakes"},
        {"variables": ["mag"]},
        {"min_magnitude": "big"},
        {"min_magnitude": True},
        {"max_depth": 5000},
        {"min_magnitude": 3, "max_magnitude": 2},
        {"min_depth": 10, "max_depth": 5},
        {"typo": 1},
    ],
)
def test_bad_queries_fail_before_network(kwargs) -> None:
    with adapter() as provider, pytest.raises(QueryError), respx.mock() as mock:
        provider.list_assets(query(**kwargs))
    assert not mock.calls


def message(**params: object) -> str:
    with adapter() as provider, pytest.raises(QueryError) as raised:
        provider.parse_params(Query(params=params), EarthquakesParams)
    return str(raised.value)


def test_bounds_are_named_with_their_ranges_and_order() -> None:
    assert message(min_magnitude="x") == "min_magnitude must be a number from -10 to 10"
    assert message(max_depth=5000) == "max_depth must be a number from -100 to 1000"
    assert (
        message(min_magnitude=3, max_magnitude=2) == "min_magnitude must not exceed max_magnitude"
    )
    assert message(min_depth=10, max_depth=5) == "min_depth must not exceed max_depth"


def test_filters_send_only_the_bounds_that_were_set() -> None:
    with adapter() as provider:
        params = provider.parse_params(Query(params={"min_magnitude": "2.5"}), EarthquakesParams)
    assert params.filters() == {"minmagnitude": "2.5"}
    assert EarthquakesParams().filters() == {}


def test_listing_counts_first_and_pins_one_csv_page_with_the_query_as_sent() -> None:
    q = query(location="Oklahoma", min_magnitude=2, max_depth=50)
    with respx.mock() as mock, adapter() as provider:
        count = mock.get(COUNT_URL).respond(200, text="92\n")
        (asset,) = provider.list_assets(q)
    sent = count.calls[0].request.url.params
    assert sent["starttime"] == "2024-05-06T00:00:00"
    assert sent["endtime"] == "2024-05-07T23:59:59.999999"  # a bare end date is its whole day
    assert (sent["minmagnitude"], sent["maxdepth"]) == ("2", "50")
    assert float(sent["minlatitude"]) < 35.5 < float(sent["maxlatitude"])
    assert float(sent["minlongitude"]) < -97.5 < float(sent["maxlongitude"])
    assert "format" not in sent and "limit" not in sent
    pinned = httpx.URL(asset.href).params
    assert str(httpx.URL(asset.href)).startswith(QUERY_URL)
    assert (pinned["format"], pinned["orderby"], pinned["limit"], pinned["offset"]) == (
        "csv",
        "time-asc",
        "20000",
        "1",
    )
    assert {k: v for k, v in pinned.items() if k in sent} == dict(sent)
    assert asset.id.startswith("comcat_20240506_20240507_") and asset.id.endswith(".csv")
    assert asset.media_type == "text/csv" and asset.bbox == q.bbox
    assert asset.time == q.time


def test_a_box_is_sent_to_six_decimals() -> None:
    with respx.mock() as mock, adapter() as provider:
        count = mock.get(COUNT_URL).respond(200, text="1")
        (asset,) = provider.list_assets(query(bbox=(-105.123456, 39.654321, -104.9, 40.0)))
    for params in (count.calls[0].request.url.params, httpx.URL(asset.href).params):
        assert [params[k] for k in ("minlatitude", "maxlatitude")] == ["39.654321", "40"]
        assert [params[k] for k in ("minlongitude", "maxlongitude")] == ["-105.123456", "-104.9"]


def test_no_matching_events_is_an_empty_listing() -> None:
    with respx.mock() as mock, adapter() as provider:
        mock.get(COUNT_URL).respond(200, text="0")
        assert provider.list_assets(query(min_magnitude=9)) == []


def test_more_than_one_page_becomes_one_asset_per_page_in_time_order(monkeypatch) -> None:
    monkeypatch.setattr("usdata.providers.usgs.earthquakes.PAGE_SIZE", 40)
    with respx.mock() as mock, adapter() as provider:
        mock.get(COUNT_URL).respond(200, text="92")
        assets = provider.list_assets(query())
    offsets = [httpx.URL(a.href).params["offset"] for a in assets]
    assert offsets == ["1", "41", "81"]
    assert len({a.id for a in assets}) == 3


@pytest.mark.parametrize("text", ["Error 400: Bad Request\n", "<html>down</html>", "²"])
def test_a_count_that_is_not_a_number_is_an_upstream_failure(text: str) -> None:
    with respx.mock() as mock, adapter() as provider:
        mock.get(COUNT_URL).respond(200, text=text)
        with pytest.raises(httpx.DecodingError, match="did not return a count"):
            provider.list_assets(query())


def test_the_cli_exits_4_when_the_count_is_not_a_number() -> None:
    with respx.mock() as mock:
        mock.get(COUNT_URL).respond(200, text="<html>maintenance</html>")
        result = CliRunner().invoke(
            app,
            [
                "fetch",
                "usgs:earthquakes",
                "--dry-run",
                "--start",
                "2024-05-06",
                "--end",
                "2024-05-07",
            ],
        )
    assert result.exit_code == 4, result.output
    assert "did not return a count" in result.output


def test_fetch_downloads_the_page_bytes_unchanged(tmp_path: Path) -> None:
    with respx.mock() as mock:
        mock.get(COUNT_URL).respond(200, text="1")
        mock.get(QUERY_URL).respond(200, content=CSV)
        (item,) = fetch(get("usgs:earthquakes"), query(location="Oklahoma"), root=tmp_path)
    assert item.path.read_bytes() == CSV
    assert item.provenance.source_url == item.asset.href
