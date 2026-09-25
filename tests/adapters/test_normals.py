from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

from usdata.models import Query
from usdata.providers.base import QueryError
from usdata.providers.noaa.ghcnd import DATA_URL, SEARCH_URL, GhcnDailyParams
from usdata.providers.noaa.normals import ClimateNormals, ClimateNormalsParams
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield ClimateNormals(default_registry().get("noaa:climate-normals"), client=client)


def test_monthly_is_default_and_requests_the_whole_placeholder_year(adapter) -> None:
    query = build_query(stations="USW00013967", variables=["MLY-TMAX-NORMAL"])
    with respx.mock() as mock:
        (asset,) = adapter.list_assets(query)
        assert not mock.calls
    params = httpx.URL(asset.href).params
    assert params["dataset"] == "normals-monthly-1991-2020"
    assert params["startDate"] == "2020-01-01" and params["endDate"] == "2020-12-31"
    assert params["units"] == "metric" and params["dataTypes"] == "MLY-TMAX-NORMAL"
    assert params["includeStationLocation"] == "1"
    assert asset.id.startswith("normals-monthly-1991-2020_01-01_12-31_")
    assert asset.dataset_id == "noaa:climate-normals" and asset.media_type == "text/csv"
    assert asset.time.start == datetime(1991, 1, 1, tzinfo=UTC)
    assert asset.time.end.isoformat() == "2020-12-31T23:59:59.999999+00:00"
    assert adapter.list_assets(
        build_query(stations="USW00013967", variables=["MLY-TMAX-NORMAL"], period="monthly")
    ) == [asset]


@pytest.mark.parametrize(
    ("period", "start", "end", "first", "last"),
    [
        ("daily", "2024-02-27", "2024-03-01", "2020-02-27", "2020-03-01"),
        ("daily", "2024-02-29", "2024-02-29", "2020-02-29", "2020-02-29"),
        ("daily", None, None, "2020-01-01", "2020-12-31"),
        ("hourly", None, None, "2020-01-01", "2020-12-31"),
        ("hourly", "2024-05-06", "2024-05-06", "2020-05-06", "2020-05-06"),
        ("hourly", "2024-02-28", "2024-03-01", "2020-02-28", "2020-03-01"),
        ("hourly", "2024-05-06T12:30Z", "2024-05-06T13:30Z", "2020-05-06", "2020-05-06"),
        ("hourly", "2024-05-06T23:30-02:00", "2024-05-07T02:30Z", "2020-05-07", "2020-05-07"),
        ("monthly", "1999-03-15", "2001-04-02", "2020-03-15", "2020-04-02"),
        ("monthly", "2024-03-01T00:30+02:00", "2024-06-30T23:30-02:00", "2020-02-29", "2020-07-01"),
    ],
)
def test_windows_keep_month_and_day_and_drop_the_year(
    adapter, period, start, end, first, last
) -> None:
    query = build_query(start=start, end=end, stations="USW00013967", period=period)
    (asset,) = adapter.list_assets(query)
    params = httpx.URL(asset.href).params
    assert params["dataset"] == f"normals-{period}-1991-2020"
    assert params["startDate"] == first and params["endDate"] == last
    assert asset.id.startswith(f"normals-{period}-1991-2020_{first[5:]}_{last[5:]}_")


def test_window_crossing_the_new_year_after_utc_shift_is_rejected(adapter) -> None:
    # Ordered as given, but the UTC conversion moves the start into December 31.
    query = build_query(
        start="2024-01-01T00:30+02:00", end="2024-06-30", stations="USW00013967", period="daily"
    )
    with pytest.raises(QueryError, match="cross the new year"):
        adapter.list_assets(query)


def test_annualseasonal_sends_no_dates(adapter) -> None:
    (asset,) = adapter.list_assets(
        build_query(stations="USW00013967", period="annualseasonal", units="standard")
    )
    params = httpx.URL(asset.href).params
    assert params["dataset"] == "normals-annualseasonal-1991-2020"
    assert "startDate" not in params and "endDate" not in params
    assert params["units"] == "standard"
    assert asset.id.startswith("normals-annualseasonal-1991-2020_")


@pytest.mark.parametrize(
    ("period", "variable"), [("daily", "DLY-TMAX-NORMAL"), ("hourly", "HLY-TEMP-NORMAL")]
)
def test_geographic_discovery_searches_the_normals_period(adapter, period, variable) -> None:
    query = build_query(bbox=(-97.62, 35.38, -97.58, 35.40), period=period, variables=[variable])
    with respx.mock() as mock:
        route = mock.get(SEARCH_URL).respond(
            200, json={"count": 1, "results": [{"stations": [{"id": "USW00013967"}]}]}
        )
        assert adapter.find_stations(query) == ["USW00013967"]
        (asset,) = adapter.list_assets(query)
    for call in route.calls:
        params = call.request.url.params
        assert params["dataset"] == f"normals-{period}-1991-2020"
        assert params["startDate"] == "1991-01-01" and params["endDate"] == "2020-12-31"
        assert params["dataTypes"] == variable
        assert params["bbox"] == "35.4,-97.62,35.38,-97.58"
    params = httpx.URL(asset.href).params
    assert params["stations"] == "USW00013967" and "bbox" not in params
    assert asset.bbox == query.bbox


def test_no_matching_stations_is_empty(adapter) -> None:
    with respx.mock() as mock:
        mock.get(SEARCH_URL).respond(200, json={"count": 0, "results": []})
        assert adapter.list_assets(build_query(location="ok")) == []


def test_period_extends_the_shared_station_declaration(adapter) -> None:
    """Normals add one parameter to GHCN-Daily's, so the model extends rather than repeats it."""
    assert issubclass(ClimateNormalsParams, GhcnDailyParams)

    def message(**params: object) -> str:
        with pytest.raises(QueryError) as raised:
            adapter.parse_params(Query(params=params), ClimateNormalsParams)
        return str(raised.value)

    assert adapter.parse_params(Query(params={}), ClimateNormalsParams).period == "monthly"
    assert adapter.parse_params(Query(params={"period": "daily"}), ClimateNormalsParams).period == (
        "daily"
    )
    assert adapter.parse_params(
        Query(params={"period": "hourly"}), ClimateNormalsParams
    ).period == ("hourly")
    assert message(period="weekly") == "period must be monthly, daily, annualseasonal, or hourly"
    assert message(period=1) == "period must be monthly, daily, annualseasonal, or hourly"
    assert message(stations=[]) == "stations must not be empty"
    assert message(units="kelvin") == "units must be metric or standard"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start": "2024-01-01"},
        {"end": "2024-01-01"},
        {"period": "annualseasonal", "start": "2024-01-01", "end": "2024-12-31"},
        {"period": "weekly"},
        {"period": "hourly", "start": "2024-05-06"},
        {"period": "hourly", "start": "2024-12-31", "end": "2025-01-01"},
        {"stations": ""},
        {"stations": []},
        {"stations": [123]},
        {"units": "kelvin"},
        {"untis": "metric"},
        {"location": "ok"},
        {"text": "normals"},
    ],
)
def test_invalid_queries_rejected_before_client_creation(kwargs, monkeypatch) -> None:
    def unexpected_client():
        raise AssertionError("invalid query must fail before allocating a client")

    monkeypatch.setattr("usdata.protocols.http.client", unexpected_client)
    query = build_query(**{"stations": "USW00013967", **kwargs})
    with (
        ClimateNormals(default_registry().get("noaa:climate-normals")) as adapter,
        pytest.raises(QueryError),
    ):
        adapter.list_assets(query)


@pytest.mark.l2
def test_normals_example_uses_existing_csv_reader(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    example = (
        Path(__file__).resolve().parents[2] / "examples/datasets/noaa-climate-normals/dataset.yaml"
    )
    manifest = tmp_path / "dataset.yaml"
    manifest.write_bytes(example.read_bytes())
    source = (
        b'"STATION","LATITUDE","LONGITUDE","ELEVATION","DATE",'
        b'"MLY-PRCP-NORMAL","MLY-TMAX-NORMAL","MLY-TMIN-NORMAL"\n'
        b'"USW00013967"," 35.3889"," -97.6006"," 391.7","01","33.5","9.6","-2.6"\n'
    )
    with respx.mock() as mock:
        route = mock.get(DATA_URL).respond(200, content=source)
        (item,) = pull(manifest, root=tmp_path / "cache").fetched
    params = route.calls[0].request.url.params
    assert params["dataset"] == "normals-monthly-1991-2020" and params["units"] == "metric"
    frame = item.open_csv(dtype={"DATE": "string"})
    assert frame["DATE"].tolist() == ["01"]
    assert frame["MLY-TMAX-NORMAL"].tolist() == [9.6]
    assert frame.attrs["usdata"]["provenance"] == item.provenance.model_dump(mode="json")
    assert item.path.read_bytes() == source
    assert verify(manifest, root=tmp_path / "cache") == []


@pytest.mark.l2
def test_hourly_normals_preserve_labels_and_restore_exact_bytes(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(
        "name: hourly-normals\nsources:\n  - dataset: noaa:climate-normals\n"
        "    start: 2024-05-06\n    end: 2024-05-06\n"
        "    variables: [HLY-TEMP-NORMAL]\n"
        "    params: {stations: USW00013967, period: hourly, units: metric}\n"
    )
    source = (Path(__file__).parents[1] / "fixtures/hourly-normals.csv").read_bytes()
    with respx.mock() as mock:
        route = mock.get(DATA_URL).respond(200, content=source)
        first = pull(manifest, root=tmp_path / "cache")
        (item,) = first.fetched
        assert route.calls[0].request.url.params["dataset"] == "normals-hourly-1991-2020"
        frame = item.open_csv(dtype={"DATE": "string"})
        assert frame["DATE"].tolist() == [f"05-06T{hour:02}:00:00" for hour in range(24)]
        assert frame["HLY-TEMP-NORMAL"].iloc[0] == 16.1
        assert item.path.read_bytes() == source
        restored = pull(manifest, root=tmp_path / "restored")
    assert restored.from_lockfile and not restored.fetched[0].from_cache
    assert restored.lockfile == first.lockfile
    assert restored.fetched[0].path.read_bytes() == source
    assert route.calls[1].request.url == route.calls[0].request.url
    assert verify(manifest, root=tmp_path / "restored") == []
