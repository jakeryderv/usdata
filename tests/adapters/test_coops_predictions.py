"""CO-OPS tide-prediction query semantics and rejection of unusable responses."""

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from usdata.cli.app import app
from usdata.providers.base import QueryError
from usdata.providers.noaa.coops import CoopsTidePredictions
from usdata.query import build_query
from usdata.registry import default_registry

HILO = b"Date Time, Prediction, Type\n2024-05-06 02:19,0.837,H\n2024-05-06 06:17,0.731,L\n"


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
    return CoopsTidePredictions(default_registry().get("noaa:coops-tide-predictions"))


@pytest.fixture
def csv_bytes():
    return (Path(__file__).parents[1] / "fixtures/coops-tide-predictions.csv").read_bytes()


def test_request_is_explicit_and_equivalent_utc_bounds_are_stable():
    with adapter() as provider:
        original = query()
        (asset,) = provider.list_assets(original)
        assert [asset] == provider.list_assets(
            query(start="2024-05-05T20:00-04:00", end="2024-05-05T20:12-04:00")
        )
    assert dict(httpx.URL(asset.href).params) == {
        "station": "8518750",
        "product": "predictions",
        "begin_date": "20240506 00:00",
        "end_date": "20240506 00:12",
        "datum": "MLLW",
        "units": "metric",
        "interval": "6",
        "time_zone": "gmt",
        "format": "csv",
        "application": "usdata",
    }
    assert asset.time == original.time
    assert asset.dataset_id == "noaa:coops-tide-predictions"
    assert asset.id.startswith("predictions_8518750_") and asset.media_type == "text/csv"


@pytest.mark.parametrize(
    "raw, sent",
    [("hilo", "hilo"), ("HILO", "hilo"), ("h", "h"), (15, "15"), (" 60 ", "60")],
)
def test_interval_is_normalized_into_the_request(raw, sent):
    with adapter() as provider:
        (asset,) = provider.list_assets(query(interval=raw))
    assert httpx.URL(asset.href).params["interval"] == sent


@pytest.mark.parametrize("changes", [{"interval": "hilo"}, {"interval": "h"}, {"units": "english"}])
def test_request_semantics_change_identity(changes):
    with adapter() as provider:
        first = provider.list_assets(query())[0]
        second = provider.list_assets(query(**changes))[0]
    assert first.id != second.id and first.href != second.href


def test_predictions_may_span_a_year_on_any_interval():
    with adapter() as provider:
        for interval in ("6", "h", "hilo"):
            (asset,) = provider.list_assets(
                query(start="2024-01-01", end="2024-12-31", interval=interval)
            )
            assert asset.time and asset.time.start == datetime(2024, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    "changes",
    [
        {"station": None},
        {"station": "851875"},
        {"datum": None},
        {"datum": "bad"},
        {"units": "standard"},
        {"interval": 0},
        {"interval": "2"},
        {"interval": True},
        {"interval": 1.5},
        {"interval": "max_slack"},
        {"interval": ""},
        {"start": None},
        {"end": None},
        {"start": "2024-05-06T00:00:01Z"},
        {"end": "2025-05-08T00:00Z"},
        {"variables": ["predictions"]},
        {"text": "Battery"},
        {"bbox": (-75, 40, -74, 41)},
        {"product": "water_level"},
        {"bin": "1"},
    ],
)
def test_invalid_queries_fail_before_client_creation(changes, monkeypatch):
    def unexpected():
        raise AssertionError("invalid query allocated a client")

    monkeypatch.setattr("usdata.protocols.http.client", unexpected)
    with adapter() as provider, pytest.raises(QueryError):
        provider.list_assets(query(**changes))


@pytest.mark.l2
@pytest.mark.parametrize("interval", ["6", "hilo"])
def test_fetch_preserves_exact_csv(csv_bytes, interval, respx_mock, tmp_path):
    payload = HILO if interval == "hilo" else csv_bytes
    with adapter() as provider:
        asset = provider.list_assets(query(interval=interval, end="2024-05-06T12:00Z"))[0]
        respx_mock.get(asset.href).respond(200, content=payload)
        dest = tmp_path / "chosen.csv"
        assert provider.fetch(asset, dest) == dest
    assert dest.read_bytes() == payload
    assert list(tmp_path.iterdir()) == [dest]


@pytest.mark.l2
@pytest.mark.parametrize(
    "interval, payload",
    [
        ("6", b" The station is not a valid station or there is system error."),
        ("6", b"Date Time, Prediction\nError: No data was found.\n"),
        ("6", b"Date Time, Prediction\n"),
        ("6", b"Date Time, Prediction\n2024-05-06 00:00,high\n"),
        ("6", b"Date Time, Prediction\n2024-05-07 00:00,0.7\n"),
        ("6", b"Date Time, Prediction\n2024-05-06 00:00\n"),
        ("6", b'{"error":{"message":"No data"}}'),
        ("hilo", b"Date Time, Prediction\n2024-05-06 00:00,0.7\n"),
        ("hilo", HILO.replace(b",H\n", b",X\n")),
    ],
)
def test_bad_successful_responses_preserve_destination(interval, payload, respx_mock, tmp_path):
    dest = tmp_path / "existing.csv"
    dest.write_bytes(b"previous verified bytes")
    with adapter() as provider:
        asset = provider.list_assets(query(interval=interval, end="2024-05-06T12:00Z"))[0]
        respx_mock.get(asset.href).respond(200, content=payload)
        with pytest.raises(httpx.DecodingError, match="CO-OPS"):
            provider.fetch(asset, dest)
    assert dest.read_bytes() == b"previous verified bytes"
    assert list(tmp_path.iterdir()) == [dest]


def test_cli_dry_run_lists_the_request_without_fetching(respx_mock):
    result = CliRunner().invoke(
        app,
        [
            "fetch",
            "noaa:coops-tide-predictions",
            "--start",
            "2024-05-06T00:00Z",
            "--end",
            "2024-05-06T00:12Z",
            "-p",
            "station=8518750",
            "-p",
            "datum=MLLW",
            "-p",
            "interval=hilo",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "product=predictions" in result.stdout and "interval=hilo" in result.stdout
    assert not respx_mock.calls
