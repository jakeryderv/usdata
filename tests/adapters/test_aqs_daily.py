"""EPA AQS daily summaries: selection, the canonical form, pacing, and the reader (ADR 0040)."""

from __future__ import annotations

import json
import random
from datetime import date
from itertools import pairwise
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata import fetch
from usdata.cli import app
from usdata.models import Query
from usdata.protocols import http
from usdata.providers import Credentials, MissingCredentials, QueryError
from usdata.providers.epa import aqs
from usdata.providers.epa.aqs import SERVICE_URL, AqsDaily, AqsError, canonical
from usdata.query import build_query
from usdata.registry import default_registry

EMAIL, KEY = "someone+aqs@example.org", "k3y-VALUE-9"
SECRETS = Credentials({"USDATA_AQS_EMAIL": EMAIL, "USDATA_AQS_KEY": KEY})
DATASET = default_registry().get("epa:aqs-daily")
JUNE = {"start": "2023-06-01", "end": "2023-06-10"}


def row(site: str, day: str, standard: str | None, event: str = "No Events") -> dict:
    return {
        "state_code": "36",
        "county_code": "081",
        "site_number": site,
        "parameter_code": "88101",
        "poc": 1,
        "date_local": day,
        "sample_duration_code": "X",
        "pollutant_standard": standard,
        "method_code": "736",
        "event_type": event,
        "arithmetic_mean": 12.5,
        "units_of_measure": "Micrograms/cubic meter (LC)",
        "date_of_last_change": "2024-05-17",
    }


ROWS = [
    row("0124", "2023-06-07", "PM25 24-hour 2024", "Events Included"),
    row("0124", "2023-06-07", "PM25 24-hour 2024", "Concurred Events Excluded"),
    row("0124", "2023-06-06", "PM25 24-hour 2024"),
    row("0124", "2023-06-06", None),
    row("0125", "2023-06-06", "PM25 Annual 2024"),
]


def body(request: httpx.Request, rows: list[dict], status: str = "Success") -> dict:
    header = {"status": status, "request_time": "2026-09-23T23:27:11-04:00"}
    return {"Header": [{**header, "url": str(request.url), "rows": len(rows)}], "Data": rows}


@pytest.fixture
def adapter():
    with httpx.Client() as client, AqsDaily(DATASET, client, credentials=SECRETS) as adapter:
        yield adapter


@pytest.fixture
def unpaced(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record pacing waits instead of sleeping, from a fresh pace."""
    waits: list[float] = []
    monkeypatch.setattr(http, "sleep", waits.append)
    monkeypatch.setattr(aqs, "PACE", aqs._Pace())
    return waits


def listed(adapter: AqsDaily, **kwargs) -> list[httpx.URL]:
    with respx.mock() as mock:
        assets = adapter.list_assets(build_query(**kwargs))
        assert not mock.calls  # Listing never contacts the service.
    return [httpx.URL(asset.href) for asset in assets]


def test_a_county_location_selects_that_county_exactly(adapter) -> None:
    (url,) = listed(adapter, location="Queens County, NY", parameters="88101", **JUNE)
    assert str(url).startswith(SERVICE_URL + "byCounty?")
    assert dict(url.params) == {
        "param": "88101",
        "bdate": "20230601",
        "edate": "20230610",
        "state": "36",
        "county": "081",
    }
    assert "email" not in url.params and "key" not in url.params


def test_a_state_location_sites_and_a_box_select_as_the_adr_says(adapter) -> None:
    (state,) = listed(adapter, location="New York", parameters=88101, **JUNE)
    assert state.path.endswith("/byState") and state.params["state"] == "36"
    sites = listed(adapter, sites="36-081-0124, 36-061-0135", parameters="88101", **JUNE)
    assert [(u.params["county"], u.params["site"]) for u in sites] == [
        ("081", "0124"),
        ("061", "0135"),
    ]
    assert all(u.path.endswith("/bySite") for u in sites)
    (box,) = listed(adapter, bbox=(-74.3, 40.5, -73.7, 40.95), parameters="88101", **JUNE)
    assert box.path.endswith("/byBox")
    assert {k: box.params[k] for k in ("minlat", "maxlat", "minlon", "maxlon")} == {
        "minlat": "40.5",
        "maxlat": "40.95",
        "minlon": "-74.3",
        "maxlon": "-73.7",
    }


def test_each_calendar_year_is_its_own_request(adapter) -> None:
    with respx.mock():
        assets = adapter.list_assets(
            build_query(
                sites="36-081-0124", parameters="88101,44201", start="2022-12-30", end="2024-01-02"
            )
        )
    assert [asset.id for asset in assets] == [
        "aqs-daily_site-36-081-0124_88101-44201_20221230_20221231.json",
        "aqs-daily_site-36-081-0124_88101-44201_20230101_20231231.json",
        "aqs-daily_site-36-081-0124_88101-44201_20240101_20240102.json",
    ]
    assert [httpx.URL(a.href).params["param"] for a in assets] == ["88101,44201"] * 3
    last = assets[-1].time
    assert last is not None and last.start is not None and last.end is not None
    assert (last.start.date(), last.end.date()) == (date(2024, 1, 1), date(2024, 1, 2))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"parameters": "88101", "text": "smoke"}, "does not support text"),
        ({"parameters": "88101", "variables": ["aqi"]}, "does not support variables"),
        ({"sites": "36-081-0124"}, "parameters is required"),
        ({"parameters": "1,2,3,4,5,6", "sites": "36-081-0124"}, "integer from 10000"),
        (
            {"parameters": "11101,12101,14101,42101,42401,44201", "sites": "36-081-0124"},
            "at most 5 per request",
        ),
        ({"parameters": "88101", "sites": "36-81-124"}, "state-county-site"),
        ({"parameters": "88101"}, "needs a place"),
        (
            {"parameters": "88101", "sites": "36-081-0124", "location": "Queens County, NY"},
            "pass one of them",
        ),
        ({"parameters": "88101", "sites": "36-081-0124", "start": "2023-06-01"}, "both start"),
        ({"parameters": True, "sites": "36-081-0124"}, "integer"),
    ],
)
def test_refusals_come_before_any_request(adapter, kwargs, message) -> None:
    window = {} if "start" in kwargs else JUNE
    with respx.mock() as mock, pytest.raises(QueryError, match=message):
        adapter.list_assets(build_query(**{**window, **kwargs}))
    assert not mock.calls


def test_the_canonical_form_drops_the_echo_and_ignores_row_order() -> None:
    request = httpx.Request("GET", "https://aqs.test/x?email=a%40b&key=k")
    shuffled = ROWS[:]
    random.Random(7).shuffle(shuffled)
    first, second = canonical(body(request, ROWS)), canonical(body(request, shuffled))
    assert first == second
    written = json.loads(first)
    assert written["Header"] == [{"rows": 5, "status": "Success"}]
    assert b"key=" not in first and b"request_time" not in first
    assert [(r["site_number"], r["date_local"], r["event_type"]) for r in written["Data"]] == [
        ("0124", "2023-06-06", "No Events"),
        ("0124", "2023-06-06", "No Events"),
        ("0124", "2023-06-07", "Concurred Events Excluded"),
        ("0124", "2023-06-07", "Events Included"),
        ("0125", "2023-06-06", "No Events"),
    ]


def test_no_data_is_an_answer_and_a_failure_status_is_an_error() -> None:
    request = httpx.Request("GET", "https://aqs.test/x")
    empty = json.loads(canonical(body(request, [], "No data matched your selection")))
    assert empty["Data"] == [] and empty["Header"][0]["rows"] == 0
    failed = body(request, [], "Failed")
    failed["Header"][0]["error"] = ["Invalid email or key"]
    with pytest.raises(AqsError, match="Invalid email or key"):
        canonical(failed)


def test_fetch_sends_the_key_writes_canonical_json_and_records_why(
    tmp_path, monkeypatch, unpaced
) -> None:
    monkeypatch.setenv("USDATA_AQS_EMAIL", EMAIL)
    monkeypatch.setenv("USDATA_AQS_KEY", KEY)
    with respx.mock() as mock:
        route = mock.get(url__startswith=SERVICE_URL).mock(
            side_effect=lambda request: httpx.Response(200, json=body(request, ROWS))
        )
        (item,) = fetch(
            DATASET,
            build_query(
                sites="36-081-0124", parameters="88101", start="2023-06-01", end="2023-06-10"
            ),
            root=tmp_path,
        )
    sent = route.calls[0].request.url
    assert sent.params["email"] == EMAIL and sent.params["key"] == KEY
    # The selection in the href survives the keys being added to it.
    assert {k: sent.params[k] for k in ("param", "bdate", "edate", "state", "county", "site")} == {
        "param": "88101",
        "bdate": "20230601",
        "edate": "20230610",
        "state": "36",
        "county": "081",
        "site": "0124",
    }
    assert item.path.read_bytes() == canonical(body(route.calls[0].request, ROWS))
    assert item.provenance.transformations == list(AqsDaily.transformations)
    assert item.provenance.credentials == ["USDATA_AQS_EMAIL", "USDATA_AQS_KEY"]
    for path in tmp_path.rglob("*"):
        if path.is_file():
            text = path.read_text()
            assert KEY not in text and "someone%2Baqs" not in text and EMAIL not in text


def test_a_failure_status_writes_nothing(tmp_path, monkeypatch, unpaced) -> None:
    monkeypatch.setenv("USDATA_AQS_EMAIL", EMAIL)
    monkeypatch.setenv("USDATA_AQS_KEY", KEY)
    failed = {"Header": [{"status": "Failed", "error": ["Invalid key"]}], "Data": []}
    with respx.mock() as mock, pytest.raises(AqsError, match="Invalid key"):
        mock.get(url__startswith=SERVICE_URL).respond(200, json=failed)
        fetch(
            DATASET,
            build_query(
                sites="36-081-0124", parameters="88101", start="2023-06-01", end="2023-06-10"
            ),
            root=tmp_path,
        )
    assert not [path for path in tmp_path.rglob("*") if path.is_file()]


def test_requests_are_paced_six_seconds_apart_across_adapters(unpaced, monkeypatch) -> None:
    # Each wait reads the clock to check, except the first, then again once it may send.
    clock = iter([100.0, 101.5, 106.0, 112.5, 112.5])
    monkeypatch.setattr(aqs, "monotonic", lambda: next(clock))
    aqs.PACE.wait()  # The first request never waits.
    aqs.PACE.wait()  # 1.5 s after the first: wait out the rest of six.
    aqs.PACE.wait()  # 6.5 s after the second was sent: no wait.
    assert unpaced == [4.5]


def test_transport_retries_are_paced_like_any_request(tmp_path, monkeypatch, unpaced) -> None:
    monkeypatch.setenv("USDATA_AQS_EMAIL", EMAIL)
    monkeypatch.setenv("USDATA_AQS_KEY", KEY)
    now = [1000.0]

    def sleep(seconds: float) -> None:
        now[0] += seconds

    monkeypatch.setattr(http, "sleep", sleep)
    monkeypatch.setattr(aqs, "monotonic", lambda: now[0])
    sent: list[float] = []
    answers = iter(
        [
            lambda request: httpx.Response(503, text="<html>maintenance</html>"),
            lambda request: httpx.Response(429, headers={"Retry-After": "9"}),
            lambda request: httpx.Response(200, json=body(request, ROWS)),
        ]
    )

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(now[0])
        return next(answers)(request)

    with respx.mock() as mock:
        mock.get(url__startswith=SERVICE_URL).mock(side_effect=answer)
        fetch(
            DATASET,
            build_query(
                sites="36-081-0124", parameters="88101", start="2023-06-01", end="2023-06-10"
            ),
            root=tmp_path,
        )
    gaps = [later - earlier for earlier, later in pairwise(sent)]
    # The 503's short backoff is stretched to the pace; the 429's longer Retry-After is kept.
    assert gaps == [aqs.MIN_INTERVAL, 9.0]


def test_the_adapter_cannot_be_built_without_both_variables(monkeypatch) -> None:
    monkeypatch.setenv("USDATA_AQS_EMAIL", EMAIL)
    monkeypatch.delenv("USDATA_AQS_KEY", raising=False)
    with pytest.raises(MissingCredentials, match=r"USDATA_AQS_KEY.*#signup"):
        AqsDaily(DATASET, credentials=Credentials.from_environment(["USDATA_AQS_EMAIL"]))


def test_reader_opens_one_row_per_summary_with_local_dates(tmp_path, monkeypatch, unpaced) -> None:
    pytest.importorskip("pandas")
    monkeypatch.setenv("USDATA_AQS_EMAIL", EMAIL)
    monkeypatch.setenv("USDATA_AQS_KEY", KEY)
    with respx.mock() as mock:
        mock.get(url__startswith=SERVICE_URL).mock(
            side_effect=lambda request: httpx.Response(200, json=body(request, ROWS))
        )
        (item,) = fetch(
            DATASET,
            build_query(
                sites="36-081-0124", parameters="88101", start="2023-06-01", end="2023-06-10"
            ),
            root=tmp_path,
        )
    frame = item.open()
    assert len(frame) == 5 and frame.site_number.tolist()[0] == "0124"
    assert str(frame.date_local.dtype).startswith("datetime64") and frame.date_local.dt.tz is None
    assert frame.attrs["usdata"]["header"] == [{"rows": 5, "status": "Success"}]
    assert frame.attrs["usdata"]["provenance"]["checksum"] == item.provenance.checksum


def test_cli_dry_run_lists_hrefs_without_the_key(monkeypatch) -> None:
    monkeypatch.setenv("USDATA_AQS_EMAIL", EMAIL)
    monkeypatch.setenv("USDATA_AQS_KEY", KEY)
    with respx.mock() as mock:
        result = CliRunner().invoke(
            app,
            [
                "fetch",
                "epa:aqs-daily",
                "--dry-run",
                "--start",
                "2023-06-01",
                "--end",
                "2023-06-10",
                "-p",
                "parameters=88101",
                "-p",
                "sites=36-081-0124",
            ],
        )
    assert result.exit_code == 0, result.output
    assert not mock.calls
    assert "bySite?param=88101" in result.stdout and KEY not in result.output
    assert EMAIL not in result.output


def test_query_without_parameters_names_the_field(adapter) -> None:
    with pytest.raises(QueryError, match="parameters is required: AQS parameter code"):
        adapter.list_assets(Query(params={"sites": "36-081-0124"}))


def test_repeated_codes_collapse_and_keep_their_order(adapter) -> None:
    (url,) = listed(adapter, sites="36-081-0124", parameters="44201,88101,44201", **JUNE)
    assert url.params["param"] == "44201,88101"


def test_an_unset_key_fails_the_cli_with_exit_2(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("USDATA_AQS_EMAIL", raising=False)
    monkeypatch.delenv("USDATA_AQS_KEY", raising=False)
    result = CliRunner().invoke(
        app, ["fetch", "epa:aqs-daily", "--dry-run", "-p", "parameters=88101"]
    )
    assert result.exit_code == 2
    assert "needs USDATA_AQS_EMAIL, USDATA_AQS_KEY set" in result.output


def test_a_refusal_keeps_the_services_reason_and_not_the_key(
    tmp_path, monkeypatch, unpaced
) -> None:
    monkeypatch.setenv("USDATA_AQS_EMAIL", EMAIL)
    monkeypatch.setenv("USDATA_AQS_KEY", KEY)
    reason = "bdate: 20221231, edate: 20230101, only 1 year of data is permitted."

    def refuse(request: httpx.Request) -> httpx.Response:
        header = {"status": "Failed", "url": str(request.url), "error": [reason]}
        return httpx.Response(400, json={"Header": [header], "Data": []})

    query = build_query(
        sites="36-081-0124", parameters="88101", start="2023-06-01", end="2023-06-10"
    )
    with respx.mock() as mock, pytest.raises(AqsError) as caught:
        mock.get(url__startswith=SERVICE_URL).mock(side_effect=refuse)
        fetch(DATASET, query, root=tmp_path)
    error = caught.value
    assert str(error) == f"AQS refused the request (400): {reason}"
    assert isinstance(error, QueryError)  # The CLI exits 2 with the reason.
    cause = error.__cause__
    assert isinstance(cause, httpx.HTTPStatusError)
    for text in (str(error), str(cause), str(cause.request.url), cause.response.text):
        assert KEY not in text and "someone%2Baqs" not in text


def cli_fetch(tmp_path: Path) -> list[str]:
    return [
        "fetch",
        "epa:aqs-daily",
        "--start",
        "2023-06-01",
        "--end",
        "2023-06-10",
        "-p",
        "parameters=88101",
        "-p",
        "sites=36-081-0124",
        "--cache-dir",
        str(tmp_path),
    ]


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(503, text="<html>Down for maintenance</html>"),
        httpx.Response(500, json={"message": "internal error"}),
        httpx.Response(200, text="<html>Down for maintenance</html>"),
        httpx.Response(200, json={"Data": []}),
        httpx.Response(200, json=[]),
    ],
    ids=["503-html", "500-json-no-header", "200-html", "200-no-header", "200-list"],
)
def test_an_upstream_failure_exits_4_without_the_key(
    tmp_path, monkeypatch, unpaced, answer
) -> None:
    monkeypatch.setenv("USDATA_AQS_EMAIL", EMAIL)
    monkeypatch.setenv("USDATA_AQS_KEY", KEY)
    with respx.mock() as mock:
        mock.get(url__startswith=SERVICE_URL).mock(return_value=answer)
        result = CliRunner().invoke(app, cli_fetch(tmp_path))
    assert result.exit_code == 4, result.output
    assert "request failed" in result.output and "refused" not in result.output
    assert KEY not in result.output and "someone" not in result.output
    assert not [path for path in tmp_path.rglob("*") if path.is_file()]


def test_a_header_refusal_still_exits_2_with_its_reason(tmp_path, monkeypatch, unpaced) -> None:
    monkeypatch.setenv("USDATA_AQS_EMAIL", EMAIL)
    monkeypatch.setenv("USDATA_AQS_KEY", KEY)
    refused = {"Header": [{"status": "Failed", "error": ["Email and/or key are invalid."]}]}
    with respx.mock() as mock:
        mock.get(url__startswith=SERVICE_URL).respond(400, json=refused)
        result = CliRunner().invoke(app, cli_fetch(tmp_path))
    assert result.exit_code == 2, result.output
    assert "AQS refused the request (400): Email and/or key are invalid." in result.output
    assert KEY not in result.output


def test_a_rejected_key_says_which_variables_to_check(tmp_path, monkeypatch, unpaced) -> None:
    monkeypatch.setenv("USDATA_AQS_EMAIL", EMAIL)
    monkeypatch.setenv("USDATA_AQS_KEY", KEY)
    refused = {"Header": [{"status": "Failed", "error": ["Email and/or key are invalid."]}]}
    query = build_query(
        sites="36-081-0124", parameters="88101", start="2023-06-01", end="2023-06-10"
    )
    with respx.mock() as mock, pytest.raises(AqsError) as caught:
        mock.get(url__startswith=SERVICE_URL).respond(400, json=refused)
        fetch(DATASET, query, root=tmp_path)
    assert str(caught.value) == (
        "AQS refused the request (400): Email and/or key are invalid. "
        "Check USDATA_AQS_EMAIL and USDATA_AQS_KEY."
    )
