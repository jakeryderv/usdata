"""IEM's SPC outlook archive: types, days, geometry form, monthly assets, and empty answers."""

import io
import zipfile
from pathlib import Path

import httpx
import pytest
import respx

from usdata import build_query, get
from usdata.models import Query
from usdata.providers.base import QueryError
from usdata.providers.noaa.spc_outlooks import SERVICE_URL, SpcOutlooks, SpcOutlooksParams

DAY = {"start": "2024-05-06T00:00Z", "end": "2024-05-06T23:59Z"}


def service_zip() -> bytes:
    """A zip as the service sends it, stamped with when it was built."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in (("outlooks.shp", b"shapes"), ("outlooks.dbf", b"\x03\x7e\x0a\x08rows")):
            archive.writestr(zipfile.ZipInfo(name, date_time=(2026, 10, 8, 18, 38, 42)), data)
    return buffer.getvalue()


def adapter() -> SpcOutlooks:
    return SpcOutlooks(get("noaa:spc-outlooks"))


def query(**kwargs):
    return build_query(**{**DAY, **kwargs})


def listed(**kwargs) -> list[httpx.URL]:
    """The URLs a query's assets name; listing itself makes no request."""
    with adapter() as provider, respx.mock() as mock:
        assets = provider.list_assets(query(**kwargs))
        assert not mock.calls
    return [httpx.URL(asset.href) for asset in assets]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start": None, "end": None},
        {"end": None},
        {"text": "tornado"},
        {"variables": ["CATEGORY"]},
        {"bbox": (-97.1, 36.1, -96.0, 37.0)},
        {"location": "Oklahoma"},
        {"outlooks": "excessive_rainfall"},
        {"outlooks": ""},
        {"days": 0},
        {"days": 9},
        {"days": "1,x"},
        {"geometry": "geom"},
        {"typo": 1},
    ],
)
def test_bad_queries_fail_before_network(kwargs) -> None:
    with adapter() as provider, pytest.raises(QueryError), respx.mock() as mock:
        provider.list_assets(query(**kwargs))
    assert not mock.calls


def message(**params: object) -> str:
    with adapter() as provider, pytest.raises(QueryError) as raised:
        provider.parse_params(Query(params=params), SpcOutlooksParams)
    return str(raised.value)


def test_refusals_say_what_to_do_instead() -> None:
    assert "convective or fire, not excessive" in message(outlooks="excessive")
    assert "cake_layer or cookie_cutter" in message(geometry="layers")
    with adapter() as provider, pytest.raises(QueryError, match="clip their areas locally"):
        provider.list_assets(query(location="Oklahoma"))


def test_every_day_of_convective_outlooks_in_cake_layers_by_default() -> None:
    (url,) = listed()
    assert (url.params["type"], url.params["geom"]) == ("C", "geom_layers")
    assert "d" not in url.params


def test_types_days_and_geometry_map_to_the_service_parameters() -> None:
    (url,) = listed(outlooks="Fire,convective", days="3,1,1", geometry="cookie_cutter")
    assert url.params["type"] == "F,C"
    assert url.params["d"] == "1,3"
    assert url.params["geom"] == "geom"


def test_the_window_selects_by_issuance_with_an_exclusive_end_one_second_later() -> None:
    (url,) = listed(start="2024-05-06T05:00Z", end="2024-05-06T05:55Z")
    assert (url.params["sts"], url.params["ets"]) == (
        "2024-05-06T05:00:00Z",
        "2024-05-06T05:55:01Z",
    )


def test_a_window_becomes_one_zip_per_utc_month_with_stable_ids() -> None:
    with adapter() as provider:
        assets = provider.list_assets(query(start="2024-01-15", end="2024-03-01"))
        again = provider.list_assets(query(start="2024-01-15", end="2024-03-01"))
    assert assets == again
    assert [asset.id[:26] for asset in assets] == [
        "outlooks_20240115_20240131",
        "outlooks_20240201_20240229",
        "outlooks_20240301_20240301",
    ]
    assert all(asset.media_type == "application/zip" for asset in assets)
    assert httpx.URL(assets[-1].href).params["ets"] == "2024-03-02T00:00:00Z"


@pytest.mark.l2
def test_fetch_writes_the_canonical_zip(tmp_path: Path) -> None:
    from usdata import fetch

    with respx.mock() as mock:
        mock.get(url__startswith=SERVICE_URL).respond(200, content=service_zip())
        (item,) = fetch(get("noaa:spc-outlooks"), query(), root=tmp_path)
    with zipfile.ZipFile(item.path) as archive:
        assert archive.namelist() == ["outlooks.shp", "outlooks.dbf"]
        assert archive.read("outlooks.dbf") == b"\x03\x50\x01\x01rows"


@pytest.mark.l2
def test_a_window_with_no_outlooks_is_an_empty_zip(tmp_path: Path) -> None:
    from usdata import fetch

    with respx.mock() as mock:
        mock.get(url__startswith=SERVICE_URL).respond(
            200, text="ERROR: no results found for your query"
        )
        (item,) = fetch(get("noaa:spc-outlooks"), query(), root=tmp_path)
    with zipfile.ZipFile(item.path) as archive:
        assert archive.namelist() == []


@pytest.mark.l2
def test_any_other_text_answer_is_an_error_naming_it(tmp_path: Path) -> None:
    from usdata import fetch

    with respx.mock() as mock:
        mock.get(url__startswith=SERVICE_URL).respond(
            200, text="Requests are limited to 10 outlook years at a time."
        )
        with pytest.raises(httpx.DecodingError, match="limited to 10 outlook years"):
            fetch(get("noaa:spc-outlooks"), query(), root=tmp_path)
