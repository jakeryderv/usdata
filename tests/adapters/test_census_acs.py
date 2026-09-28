"""Census ACS 5-year estimates: selection, refusals, the fetch as served, and the reader."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata import fetch
from usdata.cli import app
from usdata.models import Query
from usdata.protocols import http
from usdata.providers import Credentials, QueryError
from usdata.providers.census.acs import SERVICE_URL, Acs5Year, CensusError
from usdata.query import build_query
from usdata.readers import open_asset
from usdata.registry import default_registry

KEY = "c3n5us-KEY-0123456789abcdef"
SECRETS = Credentials({"USDATA_CENSUS_KEY": KEY})
DATASET = default_registry().get("census:acs-5year")
VARIABLES = ["NAME", "B01003_001E", "B01003_001M"]
TABLE = (
    b'[["NAME","B01003_001E","B01003_001M","B01003_001EA","state","county"],\n'
    b'["Adair County, Oklahoma","19595","-555555555",null,"40","001"],\n'
    b'["Alfalfa County, Oklahoma","5685","-555555555",null,"40","003"]]'
)


@pytest.fixture
def adapter():
    with httpx.Client() as client, Acs5Year(DATASET, client, credentials=SECRETS) as adapter:
        yield adapter


@pytest.fixture
def keyed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USDATA_CENSUS_KEY", KEY)
    monkeypatch.setattr(http, "sleep", lambda _: None)


def listed(adapter: Acs5Year, **kwargs) -> httpx.URL:
    kwargs.setdefault("variables", VARIABLES)
    kwargs.setdefault("vintage", 2023)
    with respx.mock() as mock:
        (asset,) = adapter.list_assets(build_query(**kwargs))
        assert not mock.calls  # Listing never contacts the service.
    return httpx.URL(asset.href)


def test_a_state_location_asks_for_the_states_own_row(adapter) -> None:
    url = listed(adapter, location="Oklahoma")
    assert str(url).startswith(f"{SERVICE_URL}/2023/acs/acs5?")
    assert dict(url.params) == {"get": "NAME,B01003_001E,B01003_001M", "for": "state:40"}


def test_geography_county_with_a_state_asks_for_every_county_in_it(adapter) -> None:
    url = listed(adapter, location="Oklahoma", geography="county")
    assert url.params["for"] == "county:*" and url.params["in"] == "state:40"


def test_a_county_location_asks_for_that_county(adapter) -> None:
    url = listed(adapter, location="Osage County, OK")
    assert url.params["for"] == "county:113" and url.params["in"] == "state:40"


def test_an_asset_names_its_vintage_period_and_place(adapter) -> None:
    query = build_query(location="Oklahoma", variables=VARIABLES, vintage=2023, geography="county")
    (asset,) = adapter.list_assets(query)
    assert asset.id.startswith("acs5_2023_40-counties_") and asset.id.endswith(".json")
    assert asset.properties == {"vintage": "2023", "period": "2019-2023"}
    assert asset.time is not None and asset.time.start is not None and asset.time.end is not None
    assert (asset.time.start.year, asset.time.end.year) == (2019, 2023)
    assert (asset.time.end.month, asset.time.end.day) == (12, 31)
    assert KEY not in asset.model_dump_json()
    # A different variable list is a different asset, never a cache hit on the first.
    (other,) = adapter.list_assets(query.model_copy(update={"variables": ["NAME"]}))
    assert other.id != asset.id


def test_variables_are_upper_cased_and_repeats_dropped_in_order(adapter) -> None:
    url = listed(adapter, location="Oklahoma", variables=["name", "b01003_001e", "NAME"])
    assert url.params["get"] == "NAME,B01003_001E"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {
                "location": "Oklahoma",
                "variables": VARIABLES,
                "vintage": 2023,
                "start": "2023-01-01",
            },
            "does not support start/end; choose the five-year period with vintage",
        ),
        (
            {"bbox": (-97.7, 35.2, -97.2, 35.7), "variables": VARIABLES, "vintage": 2023},
            "does not support bbox or lat/lon; name a state or county",
        ),
        ({"variables": VARIABLES, "vintage": 2023}, "needs a location naming a state or county"),
        ({"location": "Oklahoma", "vintage": 2023}, "needs variables naming the estimates"),
        ({"location": "Oklahoma", "variables": VARIABLES}, "vintage is required"),
        ({"location": "Oklahoma", "variables": VARIABLES, "vintage": 2008}, "vintage must be"),
        (
            {"location": "Oklahoma", "variables": ["NAME", "B01003 001E"], "vintage": 2023},
            "'B01003 001E' is not a Census API variable name",
        ),
        (
            {
                "location": "Oklahoma",
                "variables": [f"B01001_{n:03}E" for n in range(51)],
                "vintage": 2023,
            },
            "given 51 variables; the service returns at most 50 per request, NAME included",
        ),
        (
            {
                "location": "Osage County, OK",
                "variables": VARIABLES,
                "vintage": 2023,
                "geography": "state",
            },
            "geography=state needs a state location, not Osage County, OK",
        ),
        (
            {"location": "Oklahoma", "variables": VARIABLES, "vintage": 2023, "geography": "tract"},
            "geography must be state or county",
        ),
    ],
)
def test_refusals_come_before_any_request(adapter, kwargs, message) -> None:
    with respx.mock() as mock, pytest.raises(QueryError, match=message):
        adapter.list_assets(build_query(**kwargs))
    assert not mock.calls


def test_fifty_variables_name_included_are_accepted(adapter) -> None:
    names = ["NAME", *(f"B01001_{n:03}E" for n in range(1, 50))]
    assert listed(adapter, location="Oklahoma", variables=names).params["get"] == ",".join(names)


def test_connecticut_before_2022_is_keyed_by_its_old_counties(adapter) -> None:
    assert listed(adapter, location="Hartford County, CT", vintage=2021).params["for"] == (
        "county:003"
    )
    with pytest.raises(QueryError, match="vintage 2021 keys Connecticut by its eight counties"):
        adapter.list_assets(
            build_query(location="Capitol Planning Region, CT", variables=VARIABLES, vintage=2021)
        )


def test_connecticut_from_2022_is_keyed_by_its_planning_regions(adapter) -> None:
    assert listed(adapter, location="Capitol Planning Region, CT", vintage=2022).params["for"] == (
        "county:110"
    )
    with pytest.raises(QueryError) as caught:
        adapter.list_assets(
            build_query(location="Hartford County, CT", variables=VARIABLES, vintage=2022)
        )
    message = str(caught.value)
    assert "vintage 2022 keys Connecticut by the planning regions" in message
    assert "Capitol Planning Region, CT; Naugatuck Valley Planning Region, CT" in message


def test_connecticut_as_a_state_is_asked_for_whichever_counties_the_vintage_has(adapter) -> None:
    for vintage in (2021, 2022):
        url = listed(adapter, location="Connecticut", geography="county", vintage=vintage)
        assert url.params["for"] == "county:*" and url.params["in"] == "state:09"


def test_fetch_sends_the_key_and_writes_the_response_as_served(tmp_path, keyed) -> None:
    with respx.mock() as mock:
        route = mock.get(url__startswith=SERVICE_URL).mock(
            return_value=httpx.Response(200, content=TABLE)
        )
        (item,) = fetch(
            DATASET,
            build_query(location="Oklahoma", variables=VARIABLES, vintage=2023, geography="county"),
            root=tmp_path,
        )
    sent = route.calls[0].request.url
    # The selection in the href survives the key being added to it.
    assert sent.params["key"] == KEY and sent.params["for"] == "county:*"
    assert sent.params["get"] == "NAME,B01003_001E,B01003_001M"
    assert item.path.read_bytes() == TABLE
    assert item.provenance.transformations == []
    assert item.provenance.credentials == ["USDATA_CENSUS_KEY"]
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert KEY not in path.read_text()


@pytest.mark.parametrize(
    ("answer", "message"),
    [
        (
            httpx.Response(
                302, headers={"location": "https://api.census.gov/data/invalid_key.html"}
            ),
            "refused the key in USDATA_CENSUS_KEY as invalid; check it, and that the activation",
        ),
        (
            httpx.Response(
                302, headers={"location": "https://api.census.gov/data/missing_key.html"}
            ),
            "answered as if no key was sent; check USDATA_CENSUS_KEY",
        ),
        (
            httpx.Response(
                400,
                text="error: unknown variable 'B99999_001E'",
                headers={"content-type": "text/plain;charset=utf-8"},
            ),
            "refused the request: unknown variable 'B99999_001E'",
        ),
        (
            httpx.Response(
                404, text="<html>Not Found</html>", headers={"content-type": "text/html"}
            ),
            "publishes no ACS 5-year vintage 2023",
        ),
        (httpx.Response(204), "has no rows for county:\\* in state:40 in ACS 5-year vintage 2023"),
    ],
)
def test_a_refusal_says_why_and_writes_nothing(tmp_path, keyed, answer, message) -> None:
    with respx.mock() as mock:
        route = mock.get(url__startswith=SERVICE_URL).mock(return_value=answer)
        with pytest.raises(CensusError, match=message) as caught:
            fetch(
                DATASET,
                build_query(
                    location="Oklahoma", variables=VARIABLES, vintage=2023, geography="county"
                ),
                root=tmp_path,
            )
    # A redirect is refused, not followed, and a refusal is not retried.
    assert route.call_count == 1
    assert KEY not in str(caught.value)
    assert not [path for path in tmp_path.rglob("*") if path.is_file()]


def test_an_upstream_failure_is_retried_then_stays_an_http_error(tmp_path, keyed) -> None:
    with respx.mock() as mock:
        route = mock.get(url__startswith=SERVICE_URL).mock(return_value=httpx.Response(503))
        with pytest.raises(httpx.HTTPStatusError) as caught:
            fetch(
                DATASET,
                build_query(location="Oklahoma", variables=VARIABLES, vintage=2023),
                root=tmp_path,
            )
    assert route.call_count == http.MAX_ATTEMPTS
    assert KEY not in str(caught.value)
    assert not [path for path in tmp_path.rglob("*") if path.is_file()]


@pytest.mark.parametrize(
    "content", [b"<html>maintenance</html>", b'{"rows": []}', b'[["A","B"],["1"]]']
)
def test_a_body_that_is_not_a_table_writes_nothing(tmp_path, keyed, content) -> None:
    with respx.mock() as mock:
        mock.get(url__startswith=SERVICE_URL).mock(
            return_value=httpx.Response(200, content=content)
        )
        with pytest.raises(httpx.DecodingError, match="something other than a table of rows"):
            fetch(
                DATASET,
                build_query(location="Oklahoma", variables=VARIABLES, vintage=2023),
                root=tmp_path,
            )
    assert not [path for path in tmp_path.rglob("*") if path.is_file()]


def test_reader_types_estimates_keeps_codes_as_text_and_sentinels_as_served(
    tmp_path, keyed
) -> None:
    pytest.importorskip("pandas")
    with respx.mock() as mock:
        mock.get(url__startswith=SERVICE_URL).mock(return_value=httpx.Response(200, content=TABLE))
        (item,) = fetch(
            DATASET,
            build_query(location="Oklahoma", variables=VARIABLES, vintage=2023, geography="county"),
            root=tmp_path,
        )
    frame = item.open()
    assert frame.columns.tolist() == json.loads(TABLE)[0]
    assert frame.B01003_001E.tolist() == [19595, 5685]
    assert str(frame.B01003_001E.dtype) == "Int64"
    # A controlled estimate's margin of error is a code, not a missing value.
    assert frame.B01003_001M.tolist() == [-555555555, -555555555]
    assert frame.county.tolist() == ["001", "003"] and frame.state.tolist() == ["40", "40"]
    assert str(frame.NAME.dtype) == "string" and str(frame.B01003_001EA.dtype) == "string"
    assert frame.attrs["usdata"]["properties"] == {"vintage": "2023", "period": "2019-2023"}
    assert frame.attrs["usdata"]["provenance"]["checksum"] == item.provenance.checksum
    # A copied file is still recognized by its name.
    copied = item.model_copy(
        update={"asset": item.asset.model_copy(update={"dataset_id": "elsewhere:copy"})}
    )
    assert open_asset(copied).equals(frame)


def test_cli_dry_run_lists_the_href_without_the_key(keyed) -> None:
    with respx.mock() as mock:
        result = CliRunner().invoke(
            app,
            [
                "fetch",
                "census:acs-5year",
                "--dry-run",
                "--location",
                "Osage County, OK",
                "--vars",
                "NAME,B01003_001E",
                "-p",
                "vintage=2023",
            ],
        )
    assert result.exit_code == 0, result.output
    assert not mock.calls
    assert "for=county%3A113" in result.stdout and KEY not in result.output


def test_an_unset_key_fails_the_cli_with_exit_2(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("USDATA_CENSUS_KEY", raising=False)
    result = CliRunner().invoke(
        app,
        ["fetch", "census:acs-5year", "--dry-run", "--location", "Oklahoma", "-p", "vintage=2023"],
    )
    assert result.exit_code == 2
    assert "needs USDATA_CENSUS_KEY set" in result.output
    assert "api.census.gov/data/key_signup.html" in result.output


def test_a_query_without_vintage_names_the_field(adapter) -> None:
    with pytest.raises(QueryError, match="vintage is required: last year of the five-year period"):
        adapter.list_assets(Query(variables=["NAME"]))
