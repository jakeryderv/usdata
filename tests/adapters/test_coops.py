"""CO-OPS query semantics and atomic rejection of successful error responses."""

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from usdata.cli.app import app
from usdata.providers.base import QueryError
from usdata.providers.noaa.coops import CoopsWaterLevels
from usdata.query import build_query
from usdata.registry import default_registry


def query(**changes):
    return build_query(
        **{
            "start": "2024-05-06T00:00Z",
            "end": "2024-05-06T00:12Z",
            "station": "8518750",
            "datum": "MLLW",
            **changes,
        }
    )


def adapter():
    return CoopsWaterLevels(default_registry().get("noaa:coops-water-levels"))


@pytest.fixture
def csv_bytes():
    return (Path(__file__).parents[1] / "fixtures/coops-water-levels.csv").read_bytes()


def test_request_is_explicit_and_equivalent_utc_bounds_are_stable():
    with adapter() as provider:
        original = query()
        (asset,) = provider.list_assets(original)
        assert [asset] == provider.list_assets(
            query(start="2024-05-05T20:00-04:00", end="2024-05-05T20:12-04:00")
        )
    assert dict(httpx.URL(asset.href).params) == {
        "station": "8518750",
        "product": "water_level",
        "begin_date": "20240506 00:00",
        "end_date": "20240506 00:12",
        "datum": "MLLW",
        "units": "metric",
        "time_zone": "gmt",
        "format": "csv",
        "application": "usdata",
    }
    assert asset.time == original.time
    assert asset.dataset_id == "noaa:coops-water-levels"
    assert asset.media_type == "text/csv"


@pytest.mark.parametrize(
    "changes",
    [
        {"station": "8724580"},
        {"datum": "MSL"},
        {"units": "english"},
        {"end": "2024-05-06T00:18Z"},
        {"start": "2024-05-06T00:06Z"},
    ],
)
def test_request_semantics_change_identity(changes):
    with adapter() as provider:
        first = provider.list_assets(query())[0]
        second = provider.list_assets(query(**changes))[0]
    assert first.id != second.id and first.href != second.href


@pytest.mark.parametrize(
    "changes",
    [
        {"station": None},
        {"station": 8518750},
        {"station": True},
        {"station": ""},
        {"station": "851875"},
        {"station": "85187500"},
        {"station": "８５１８７５０"},  # noqa: RUF001 - reject non-ASCII digit lookalikes
        {"station": "8518750,8724580"},
        {"datum": None},
        {"datum": "bad"},
        {"datum": []},
        {"units": "standard"},
        {"units": []},
        {"start": None},
        {"end": None},
        {"start": "2024-05-06T00:00:01Z"},
        {"end": "2024-05-06T00:12:00.1Z"},
        {"end": "2024-06-03T00:01Z"},
        {"variables": ["water_level"]},
        {"text": "Battery"},
        {"bbox": (-75, 40, -74, 41)},
        {"product": "predictions"},
        {"time_zone": "lst"},
    ],
)
def test_invalid_queries_fail_before_client_creation(changes, monkeypatch):
    def unexpected():
        raise AssertionError("invalid query allocated a client")

    monkeypatch.setattr("usdata.protocols.http.client", unexpected)
    with adapter() as provider, pytest.raises(QueryError):
        provider.list_assets(query(**changes))


def test_interval_limit_inclusive_and_naive_dates_use_utc():
    with adapter() as provider:
        (asset,) = provider.list_assets(query(start="2024-05-06", end="2024-06-03"))
    assert asset.time is not None
    assert asset.time.start == datetime(2024, 5, 6, tzinfo=UTC)
    assert httpx.URL(asset.href).params["end_date"] == "20240603 00:00"


@pytest.mark.l2
@pytest.mark.parametrize("preliminary", [False, True])
def test_fetch_preserves_exact_csv_and_missing_observations(
    csv_bytes, preliminary, respx_mock, tmp_path
):
    payload = (
        csv_bytes.replace(b",v\n", b",p\n").replace(b",1.765,", b",,", 1)
        if preliminary
        else csv_bytes
    )
    with adapter() as provider:
        asset = provider.list_assets(query())[0]
        respx_mock.get(asset.href).respond(200, content=payload)
        dest = tmp_path / "chosen.csv"
        assert provider.fetch(asset, dest) == dest
    assert dest.read_bytes() == payload
    assert list(tmp_path.iterdir()) == [dest]


@pytest.mark.l2
@pytest.mark.parametrize(
    "kind",
    [
        "no-data",
        "header-only",
        "json",
        "html",
        "ragged",
        "bad-time",
        "outside",
        "bad-quality",
        "bad-value",
        "duplicate-header",
        "encoding",
    ],
)
def test_bad_successful_responses_preserve_destination(csv_bytes, kind, respx_mock, tmp_path):
    header = csv_bytes.splitlines(keepends=True)[0]
    payloads = {
        "no-data": header
        + b"Error: No data was found. This product may not be offered at this station "
        b"at the requested time.\n",
        "header-only": header,
        "json": b'{"error":{"message":"No data"}}',
        "html": b"<html>Upstream error</html>",
        "ragged": header + b"2024-05-06 00:00,1.2\n",
        "bad-time": csv_bytes.replace(b"2024-05-06", b"not-a-date"),
        "outside": csv_bytes.replace(b"2024-05-06", b"2024-05-07"),
        "bad-quality": csv_bytes.replace(b",v\n", b",unknown\n"),
        "bad-value": csv_bytes.replace(b",1.765,", b",error,"),
        "duplicate-header": csv_bytes.replace(b"Sigma", b"Water Level"),
        "encoding": b"\xff\xfe",
    }
    dest = tmp_path / "existing.csv"
    dest.write_bytes(b"previous verified bytes")
    with adapter() as provider:
        asset = provider.list_assets(query())[0]
        respx_mock.get(asset.href).respond(200, content=payloads[kind])
        with pytest.raises(httpx.DecodingError, match="CO-OPS"):
            provider.fetch(asset, dest)
    assert dest.read_bytes() == b"previous verified bytes"
    assert list(tmp_path.iterdir()) == [dest]


@pytest.mark.l2
def test_invalid_station_http_error_is_preserved(respx_mock, tmp_path):
    with adapter() as provider:
        asset = provider.list_assets(query(station="0000000"))[0]
        route = respx_mock.get(asset.href).respond(400, text="Error: invalid station")
        with pytest.raises(httpx.HTTPStatusError) as error:
            provider.fetch(asset, tmp_path / "absent.csv")
    assert error.value.response.status_code == 400 and route.call_count == 1
    assert list(tmp_path.iterdir()) == []


@pytest.mark.l2
def test_cli_reports_no_data_as_upstream_failure(csv_bytes, respx_mock, tmp_path):
    with adapter() as provider:
        asset = provider.list_assets(query())[0]
    respx_mock.get(asset.href).respond(
        200, content=csv_bytes.splitlines(keepends=True)[0] + b"Error: No data was found.\n"
    )
    result = CliRunner().invoke(
        app,
        [
            "fetch",
            "noaa:coops-water-levels",
            "--start",
            "2024-05-06T00:00Z",
            "--end",
            "2024-05-06T00:12Z",
            "-p",
            "station=8518750",
            "-p",
            "datum=MLLW",
            "--cache-dir",
            str(tmp_path),
            "--no-progress",
        ],
    )
    assert result.exit_code == 4
    assert "CO-OPS" in result.output
    assert not list(tmp_path.rglob("*.csv"))
    assert not list(tmp_path.rglob("*.json"))
