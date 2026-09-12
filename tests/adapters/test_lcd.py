from pathlib import Path

import httpx
import pytest
import respx

from usdata.providers.base import QueryError
from usdata.providers.noaa.ghcnd import DATA_URL, SEARCH_URL
from usdata.providers.noaa.lcd import LocalClimatologicalData
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield LocalClimatologicalData(default_registry().get("noaa:lcd"), client=client)


def test_request_names_the_lcd_dataset_and_whole_days(adapter) -> None:
    query = build_query(
        start="2024-05-06T18:00Z",
        end="2024-05-08",
        stations="72353013967",
        variables=["HourlyDryBulbTemperature", "DailyPrecipitation"],
    )
    with respx.mock() as mock:
        (asset,) = adapter.list_assets(query)
        assert not mock.calls
    params = httpx.URL(asset.href).params
    assert params["dataset"] == "local-climatological-data"
    assert params["stations"] == "72353013967"
    assert params["startDate"] == "2024-05-06" and params["endDate"] == "2024-05-08"
    assert params["dataTypes"] == "HourlyDryBulbTemperature,DailyPrecipitation"
    assert params["units"] == "metric" and params["includeStationLocation"] == "1"
    assert asset.dataset_id == "noaa:lcd" and asset.media_type == "text/csv"
    assert asset.id.startswith("local-climatological-data_2024-05-06_2024-05-08_")


def test_stations_are_chunked_ten_per_asset(adapter) -> None:
    stations = [f"7235301{index:04d}" for index in range(23)]
    with respx.mock() as mock:
        assets = adapter.list_assets(
            build_query(start="2024-05-06", end="2024-05-06", stations=stations)
        )
        assert not mock.calls
    assert [len(httpx.URL(a.href).params["stations"].split(",")) for a in assets] == [10, 10, 3]
    assert len({a.id for a in assets}) == 3


def test_geographic_discovery_searches_the_lcd_dataset(adapter) -> None:
    query = build_query(bbox=(-97.65, 35.35, -97.55, 35.45), start="2024-05-06", end="2024-05-07")
    with respx.mock() as mock:
        route = mock.get(SEARCH_URL).respond(
            200, json={"count": 1, "results": [{"stations": [{"id": "72353013967"}]}]}
        )
        (asset,) = adapter.list_assets(query)
    params = route.calls[0].request.url.params
    assert params["dataset"] == "local-climatological-data"
    assert params["bbox"] == "35.45,-97.65,35.35,-97.55"
    assert httpx.URL(asset.href).params["stations"] == "72353013967"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start": None},
        {"end": None},
        {"stations": ""},
        {"stations": [123]},
        {"units": "kelvin"},
        {"report_type": "FM-15"},
        {"location": "ok"},
        {"text": "hourly"},
    ],
)
def test_invalid_queries_rejected_before_client_creation(kwargs, monkeypatch) -> None:
    def unexpected_client():
        raise AssertionError("invalid query must fail before allocating a client")

    monkeypatch.setattr("usdata.protocols.http.client", unexpected_client)
    query = build_query(
        **{"start": "2024-05-06", "end": "2024-05-07", "stations": "72353013967", **kwargs}
    )
    with (
        LocalClimatologicalData(default_registry().get("noaa:lcd")) as adapter,
        pytest.raises(QueryError),
    ):
        adapter.list_assets(query)


@pytest.mark.l2
def test_hourly_example_reads_report_types_with_the_csv_reader(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    example = Path(__file__).resolve().parents[2] / "examples/hourly-observations/dataset.yaml"
    manifest = tmp_path / "dataset.yaml"
    manifest.write_bytes(example.read_bytes())
    source = (
        b'"STATION","DATE","REPORT_TYPE","SOURCE","HourlyDryBulbTemperature",'
        b'"DailyMaximumDryBulbTemperature"\n'
        b'"72353013967","2024-05-06T00:52:00","FM-15","7","16.1",\n'
        b'"72353013967","2024-05-06T13:52:00","FM-15","7","27.2s",\n'
        b'"72353013967","2024-05-06T23:59:00","SOD  ","6",,"27.8"\n'
    )
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(200, content=source)
        (item,) = pull(manifest, root=tmp_path / "cache").fetched
    frame = item.open(parse_dates=["DATE"])
    assert frame["REPORT_TYPE"].str.strip().tolist() == ["FM-15", "FM-15", "SOD"]
    assert frame["DATE"].dt.hour.tolist() == [0, 13, 23]
    assert item.path.read_bytes() == source
    assert verify(manifest, root=tmp_path / "cache") == []
