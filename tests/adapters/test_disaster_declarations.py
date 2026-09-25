"""OpenFEMA adapter: the place and period filters, count-then-page listing, and the CSV path."""

import httpx
import pytest
import respx

from usdata import build_query, get
from usdata.models import Query
from usdata.providers.base import QueryError
from usdata.providers.fema.declarations import (
    PAGE_SIZE,
    SERVICE_URL,
    DeclarationsParams,
    DisasterDeclarations,
)

CSV = (
    b"femaDeclarationString,disasterNumber,state,declarationType,declarationDate,incidentType,"
    b"incidentBeginDate,incidentEndDate,fipsStateCode,fipsCountyCode,placeCode,designatedArea\n"
    b"DR-4776-OK,4776,OK,DR,2024-04-30T00:00:00.000Z,Tornado,2024-04-25T00:00:00.000Z,"
    b"2024-05-09T00:00:00.000Z,40,113,99113,Osage (County)\n"
)
PERIOD = "incidentBeginDate le '2024-05-06' and incidentEndDate ge '2024-05-06'"


def adapter() -> DisasterDeclarations:
    return DisasterDeclarations(get("fema:disaster-declarations"))


def query(**kwargs):
    return build_query(**{"start": "2024-05-06", "end": "2024-05-06", **kwargs})


def counted(mock: respx.MockRouter, count: int) -> respx.Route:
    """Answer the count request, which is the one that asks for no format."""
    return mock.get(SERVICE_URL, params={"$inlinecount": "allpages"}).respond(
        200, json={"metadata": {"count": count}, "DisasterDeclarationsSummaries": []}
    )


def listed(count: int = 1, **kwargs) -> tuple[str, list]:
    """The ``$filter`` a query sends and the assets it lists."""
    with adapter() as provider, respx.mock() as mock:
        route = counted(mock, count)
        assets = provider.list_assets(query(**kwargs))
    return route.calls[0].request.url.params["$filter"], assets


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start": None, "end": None},
        {"end": None},
        {"text": "tornado"},
        {"variables": ["state"]},
        {"bbox": (-97.1, 36.1, -96.0, 37.0)},
        {"lat": 36.6, "lon": -96.4},
        {"state": "Oklahoma"},
        {"state": "O1"},
        {"fips": "4011"},
        {"fips": 40113},
        {"state": "OK", "fips": "40113"},
        {"location": "Oklahoma", "state": "OK"},
        {"location": "Osage County, OK", "fips": "40113"},
        {"declaration_type": "XX"},
        {"incident_type": "Tornado' or 1 eq 1 or 'a' eq 'a"},
        {"incident_type": ""},
        {"include_open": "yes"},
        {"include_open": 1},
        {"typo": 1},
    ],
)
def test_bad_queries_fail_before_network(kwargs) -> None:
    with adapter() as provider, pytest.raises(QueryError), respx.mock() as mock:
        provider.list_assets(query(**kwargs))
    assert not mock.calls


def message(**params: object) -> str:
    with adapter() as provider, pytest.raises(QueryError) as raised:
        provider.parse_params(Query(params=params), DeclarationsParams)
    return str(raised.value)


def test_refusals_say_what_to_do_instead() -> None:
    assert "pass state or fips, not both" in message(state="OK", fips="40113")
    assert "two-letter postal code such as OK" in message(state="Oklahoma")
    assert "five-digit county FIPS code such as 40113" in message(fips="113")
    assert "must be DR, EM, or FM" in message(declaration_type="dr,xx")
    assert "include_open must be true or false" in message(include_open="yes")
    with adapter() as provider, pytest.raises(QueryError) as bare:
        provider.list_assets(query(lat=36.6, lon=-96.4))
    assert str(bare.value) == (
        "fema:disaster-declarations does not support bbox or lat/lon; name a state or county "
        "with location, or pass state or fips"
    )
    with adapter() as provider, pytest.raises(QueryError, match="a location and a state or fips"):
        provider.list_assets(query(location="Oklahoma", state="OK"))


def test_a_window_selects_by_incident_period_with_date_only_bounds() -> None:
    where, _ = listed()
    assert where == PERIOD
    # Full timestamps match nothing on this service, so even a timed window sends dates alone.
    timed, _ = listed(start="2024-05-06T03:39Z", end="2024-05-07T18:00Z")
    assert timed == "incidentBeginDate le '2024-05-07' and incidentEndDate ge '2024-05-06'"


def test_incidents_with_no_end_date_are_left_out_unless_asked_for() -> None:
    assert "eq null" not in listed()[0]
    for value in (True, "true", "TRUE"):
        where, _ = listed(include_open=value)
        assert where == (
            "incidentBeginDate le '2024-05-06' and "
            "(incidentEndDate ge '2024-05-06' or incidentEndDate eq null)"
        )
    assert "eq null" not in listed(include_open="false")[0]


def test_a_state_is_selected_by_location_or_by_param() -> None:
    assert listed(location="Oklahoma")[0] == f"{PERIOD} and fipsStateCode eq '40'"
    assert listed(location="ok")[0] == listed(location="40")[0]
    assert listed(state="ok")[0] == f"{PERIOD} and state eq 'OK'"


def test_a_county_also_returns_its_states_statewide_designations() -> None:
    expected = (
        f"{PERIOD} and fipsStateCode eq '40' and "
        "(fipsCountyCode eq '113' or designatedArea eq 'Statewide')"
    )
    assert listed(location="Osage County, OK")[0] == expected
    assert listed(location="40113")[0] == expected
    assert listed(fips="40113")[0] == expected


def test_type_filters_join_one_or_several_values() -> None:
    where, _ = listed(state="OK", incident_type="Tornado", declaration_type="dr")
    assert where == (
        f"{PERIOD} and state eq 'OK' and incidentType eq 'Tornado' and declarationType eq 'DR'"
    )
    several, _ = listed(incident_type="Tornado,Severe Storm", declaration_type=["DR", "em"])
    assert several == (
        f"{PERIOD} and (incidentType eq 'Tornado' or incidentType eq 'Severe Storm') "
        "and (declarationType eq 'DR' or declarationType eq 'EM')"
    )


def test_listing_counts_first_and_pages_under_one_order() -> None:
    _, assets = listed(PAGE_SIZE * 2 + 1, state="OK")
    assert len(assets) == 3 and len({asset.id for asset in assets}) == 3
    urls = [httpx.URL(asset.href) for asset in assets]
    assert [url.params["$skip"] for url in urls] == ["0", str(PAGE_SIZE), str(PAGE_SIZE * 2)]
    for url in urls:
        assert url.params["$top"] == str(PAGE_SIZE) and url.params["$format"] == "csv"
        assert url.params["$orderby"] == "declarationDate,id"
        assert url.params["$filter"] == f"{PERIOD} and state eq 'OK'"
    assert all(asset.media_type == "text/csv" and asset.time for asset in assets)
    assert all(asset.id.startswith("declarations_20240506_20240506_") for asset in assets)


def test_the_same_query_lists_the_same_ids_and_a_different_one_does_not() -> None:
    first = listed(state="OK")[1][0].id
    assert listed(state="OK")[1][0].id == first
    assert listed(state="TX")[1][0].id != first


def test_no_matching_declaration_lists_no_asset() -> None:
    assert listed(0, state="OK")[1] == []


def test_a_location_keeps_its_box_on_the_asset_and_a_param_has_none() -> None:
    assert listed(location="Oklahoma")[1][0].bbox is not None
    assert listed(state="OK")[1][0].bbox is None


@pytest.mark.parametrize(
    "content",
    [b'{"metadata": {}}', b'{"metadata": {"count": "25"}}', b"[]", b"<html>maintenance</html>"],
)
def test_a_response_without_a_usable_count_is_an_upstream_failure(content) -> None:
    with adapter() as provider, respx.mock() as mock:
        mock.get(SERVICE_URL).respond(200, content=content)
        with pytest.raises(httpx.DecodingError, match="did not return a count") as raised:
            provider.list_assets(query(state="OK"))
    assert not isinstance(raised.value, ValueError)  # The CLI exits 4, not 2.


@pytest.mark.l2
def test_fetch_writes_the_page_and_the_reader_keeps_fips_codes_as_text(tmp_path) -> None:
    from usdata import fetch

    with respx.mock() as mock:
        counted(mock, 1)
        mock.get(SERVICE_URL, params={"$format": "csv"}).respond(200, content=CSV)
        (item,) = fetch(
            get("fema:disaster-declarations"), query(location="Osage County, OK"), root=tmp_path
        )
    assert item.path.read_bytes() == CSV
    pandas = pytest.importorskip("pandas")
    frame = item.open()
    assert isinstance(frame, pandas.DataFrame)
    assert frame.fipsStateCode.tolist() == ["40"] and frame.fipsCountyCode.tolist() == ["113"]
    assert frame.placeCode.tolist() == ["99113"]
