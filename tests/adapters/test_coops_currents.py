"""Explicit bin selection, native observations, and rejection before cache writes."""

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from usdata.cli.app import app
from usdata.providers.base import QueryError
from usdata.providers.noaa.coops import CoopsCurrents
from usdata.query import build_query
from usdata.registry import default_registry


def query(**changes):
    return build_query(
        **{
            "start": "2025-05-06T00:02Z",
            "end": "2025-05-06T00:14Z",
            "station": "cb0102",
            "bin": 4,
            **changes,
        }
    )


def adapter():
    return CoopsCurrents(default_registry().get("noaa:coops-currents"))


@pytest.fixture
def csv_bytes():
    return (Path(__file__).parents[1] / "fixtures/coops-currents.csv").read_bytes()


def test_explicit_request_and_normalized_identity():
    with adapter() as provider:
        (asset,) = provider.list_assets(query())
        assert [asset] == provider.list_assets(
            query(start="2025-05-05T20:02-04:00", end="2025-05-05T20:14-04:00", bin="04")
        )
    assert dict(httpx.URL(asset.href).params) == {
        "station": "cb0102",
        "product": "currents",
        "begin_date": "20250506 00:02",
        "end_date": "20250506 00:14",
        "bin": "4",
        "units": "metric",
        "time_zone": "gmt",
        "format": "csv",
        "application": "usdata",
    }
    assert asset.dataset_id == "noaa:coops-currents"
    assert asset.media_type == "text/csv"
    assert asset.time == query().time


@pytest.mark.parametrize(
    "changes",
    [{"station": "CFR1624"}, {"bin": 9}, {"units": "english"}, {"end": "2025-05-06"}],
)
def test_distinct_selection_has_distinct_asset(changes):
    with adapter() as provider:
        first = provider.list_assets(query())[0]
        second = provider.list_assets(query(**changes))[0]
    assert first.id != second.id and first.href != second.href


@pytest.mark.parametrize(
    "changes",
    [
        {"station": None},
        {"station": 1234567},
        {"station": True},
        {"station": ""},
        {"station": " cb0102"},
        {"station": "cb0102,cb1401"},
        {"station": "cb０１０２"},  # noqa: RUF001 - reject non-ASCII lookalikes
        {"station": "../cb0102"},
        {"bin": None},
        {"bin": 0},
        {"bin": -1},
        {"bin": True},
        {"bin": 4.0},
        {"bin": "4.0"},
        {"bin": "4,9"},
        {"bin": "４"},  # noqa: RUF001
        {"bin": [4]},
        {"units": "standard"},
        {"start": None},
        {"end": None},
        {"start": "2025-05-06T00:02:01Z"},
        {"end": "2025-05-06T00:14:00.1Z"},
        {"end": "2025-06-03T00:03Z"},
        {"bbox": (-77, 36, -76, 37)},
        {"text": "Cape Henry"},
        {"variables": ["Speed"]},
        {"datum": "MLLW"},
        {"interval": "h"},
        {"product": "currents_predictions"},
        {"time_zone": "lst"},
        {"expand": "detailed"},
    ],
)
def test_invalid_queries_do_not_allocate_transport(changes, monkeypatch):
    def unexpected():
        raise AssertionError("invalid query allocated a client")

    monkeypatch.setattr("usdata.protocols.http.client", unexpected)
    with adapter() as provider, pytest.raises(QueryError):
        provider.list_assets(query(**changes))


def test_bare_day_and_window_boundary():
    with adapter() as provider:
        (asset,) = provider.list_assets(query(start="2025-05-06", end="2025-05-06"))
        assert asset.time and asset.time.end == datetime(2025, 5, 6, 23, 59, tzinfo=UTC)
        provider.list_assets(query(start="2025-05-06", end="2025-06-03T00:00Z"))
        with pytest.raises(QueryError, match="at most 28 days"):
            provider.list_assets(query(start="2025-05-06", end="2025-06-03"))


@pytest.mark.l2
@pytest.mark.parametrize("missing", [False, True])
def test_raw_csv_and_missing_measurements_are_preserved(csv_bytes, missing, respx_mock, tmp_path):
    payload = csv_bytes
    if missing:
        payload = payload.replace(b"17.3,285", b",").replace(b"2025-05-06 00:08,18.5,286,4\n", b"")
    dest = tmp_path / "chosen.csv"
    with adapter() as provider:
        asset = provider.list_assets(query())[0]
        respx_mock.get(asset.href).respond(200, content=payload)
        assert provider.fetch(asset, dest) == dest
    assert dest.read_bytes() == payload
    assert list(tmp_path.iterdir()) == [dest]


@pytest.mark.l2
@pytest.mark.parametrize(
    "before,after",
    [
        (b"17.3", b"error"),
        (b"17.3", b"nan"),
        (b"17.3", b"inf"),
        (b"17.3", b"-1"),
        (b"285", b"nan"),
        (b"285", b"361"),
        (b"285", b"-1"),
        (b",4\n", b",9\n"),
        (b",4\n", b",4.0\n"),
        (b",4\n", b",\n"),
        (b"2025-05-06", b"2025-05-07"),
        (b"00:02", b"bad-time"),
        (b"17.3,285,4", b"17.3,285"),
        (b"Direction", b"Speed"),
    ],
)
def test_malformed_response_keeps_existing_destination(
    csv_bytes, before, after, respx_mock, tmp_path
):
    assert_bad_response(csv_bytes.replace(before, after), respx_mock, tmp_path)


@pytest.mark.l2
@pytest.mark.parametrize(
    "payload",
    [
        b"Date Time, Speed, Direction, Bin \n",
        b"Date Time, Speed, Direction, Bin \nError: No data was found.\n",
        b'{"error":{"message":"No data"}}',
        b"<html>Upstream error</html>",
        b"\xff\xfe",
    ],
)
def test_empty_or_error_documents_keep_existing_destination(payload, respx_mock, tmp_path):
    assert_bad_response(payload, respx_mock, tmp_path)


def assert_bad_response(payload, respx_mock, tmp_path):
    dest = tmp_path / "existing.csv"
    dest.write_bytes(b"previous verified bytes")
    with adapter() as provider:
        asset = provider.list_assets(query())[0]
        respx_mock.get(asset.href).respond(200, content=payload)
        with pytest.raises(httpx.DecodingError, match="CO-OPS"):
            provider.fetch(asset, dest)
    assert dest.read_bytes() == b"previous verified bytes"
    assert list(tmp_path.iterdir()) == [dest]


@pytest.mark.l2
def test_invalid_bin_http_error_does_not_write_files(respx_mock, tmp_path):
    with adapter() as provider:
        asset = provider.list_assets(query(bin=999))[0]
        respx_mock.get(asset.href).respond(400, text="Wrong Bin Number was supplied")
        with pytest.raises(httpx.HTTPStatusError) as error:
            provider.fetch(asset, tmp_path / "absent.csv")
    assert error.value.response.status_code == 400
    assert list(tmp_path.iterdir()) == []


@pytest.mark.l2
def test_cli_no_data_is_an_upstream_failure(respx_mock, tmp_path):
    with adapter() as provider:
        asset = provider.list_assets(query())[0]
    respx_mock.get(asset.href).respond(200, text="Error: No data was found.")
    result = CliRunner().invoke(
        app,
        [
            "fetch",
            "noaa:coops-currents",
            "--start",
            "2025-05-06T00:02Z",
            "--end",
            "2025-05-06T00:14Z",
            "-p",
            "station=cb0102",
            "-p",
            "bin=4",
            "--cache-dir",
            str(tmp_path),
            "--no-progress",
        ],
    )
    assert result.exit_code == 4 and "CO-OPS" in result.output
    assert not list(tmp_path.rglob("*.csv"))
    assert not list(tmp_path.rglob("*.json"))
