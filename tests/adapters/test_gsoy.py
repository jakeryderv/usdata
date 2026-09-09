from pathlib import Path

import httpx
import pytest
import respx

from usdata.providers.base import QueryError
from usdata.providers.noaa.ghcnd import DATA_URL, SEARCH_URL
from usdata.providers.noaa.gsoy import GlobalSummaryYearly
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield GlobalSummaryYearly(default_registry().get("noaa:gsoy"), client=client)


@pytest.mark.parametrize(
    ("start", "end", "first_year", "last_year"),
    [
        ("2024-05-06", "2024-05-07", "2024", "2024"),
        ("2024-02-29", "2024-02-29", "2024", "2024"),
        ("2023-12-31", "2024-01-01", "2023", "2024"),
        ("2024-01-01T00:30+02:00", "2024-01-01T00:30+02:00", "2023", "2023"),
        ("2023-12-31T23:30-02:00", "2023-12-31T23:30-02:00", "2024", "2024"),
    ],
)
def test_whole_year_urls_and_asset_coverage(adapter, start, end, first_year, last_year) -> None:
    query = build_query(start=start, end=end, stations="USW00013967", variables=["PRCP"])
    original = query.model_dump()
    with respx.mock() as mock:
        (asset,) = adapter.list_assets(query)
        assert not mock.calls
    params = httpx.URL(asset.href).params
    assert params["dataset"] == "global-summary-of-the-year"
    assert params["startDate"] == first_year + "-01-01"
    assert params["endDate"] == last_year + "-12-31"
    assert params["units"] == "metric" and params["dataTypes"] == "PRCP"
    assert asset.dataset_id == "noaa:gsoy" and asset.media_type == "text/csv"
    assert asset.time.start.isoformat() == first_year + "-01-01T00:00:00+00:00"
    assert asset.time.end.isoformat() == last_year + "-12-31T23:59:59.999999+00:00"
    equivalent = build_query(
        start=first_year + "-01-01",
        end=last_year + "-12-31",
        stations="USW00013967",
        variables=["PRCP"],
    )
    assert adapter.list_assets(equivalent)[0] == asset
    assert query.model_dump() == original


def test_geographic_discovery_uses_normalized_years(adapter) -> None:
    query = build_query(
        bbox=(-97.62, 35.38, -97.58, 35.40),
        start="2024-05-06",
        end="2024-05-07",
        variables=["PRCP", "TAVG"],
        units="standard",
    )
    with respx.mock() as mock:
        route = mock.get(SEARCH_URL).respond(
            200,
            json={"count": 1, "results": [{"stations": [{"id": "USW00013967"}]}]},
        )
        assert adapter.find_stations(query) == ["USW00013967"]
        (asset,) = adapter.list_assets(query)
    for call in route.calls:
        params = call.request.url.params
        assert params["dataset"] == "global-summary-of-the-year"
        assert params["startDate"] == "2024-01-01" and params["endDate"] == "2024-12-31"
        assert params["dataTypes"] == "PRCP,TAVG"
        assert params["bbox"] == "35.4,-97.62,35.38,-97.58"
    params = httpx.URL(asset.href).params
    assert params["stations"] == "USW00013967" and params["units"] == "standard"
    assert "bbox" not in params


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start": None},
        {"end": None},
        {"stations": ""},
        {"stations": []},
        {"stations": [123]},
        {"units": "kelvin"},
        {"untis": "metric"},
        {"location": "ok"},
        {"text": "precipitation"},
    ],
)
def test_invalid_queries_rejected_before_client_creation(kwargs, monkeypatch) -> None:
    def unexpected_client():
        raise AssertionError("invalid query must fail before allocating a client")

    monkeypatch.setattr("usdata.protocols.http.client", unexpected_client)
    query = build_query(
        **{"start": "2024-05-06", "end": "2024-05-07", "stations": "USW00013967", **kwargs}
    )
    with (
        GlobalSummaryYearly(default_registry().get("noaa:gsoy")) as adapter,
        pytest.raises(QueryError),
    ):
        adapter.list_assets(query)


def test_no_matching_stations_is_empty(adapter) -> None:
    with respx.mock() as mock:
        mock.get(SEARCH_URL).respond(200, json={"count": 0, "results": []})
        assert (
            adapter.list_assets(build_query(location="ok", start="2024-01-01", end="2024-12-31"))
            == []
        )


@pytest.mark.l2
def test_annual_example_uses_existing_csv_reader(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    example = Path(__file__).resolve().parents[2] / "examples/annual-climate/dataset.yaml"
    manifest = tmp_path / "dataset.yaml"
    manifest.write_bytes(example.read_bytes())
    source = b'"STATION","DATE","PRCP","TAVG"\n"USW00013967","2024","900.0","18.0"\n'
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(200, content=source)
        (item,) = pull(manifest, root=tmp_path / "cache").fetched
    frame = item.open(dtype={"DATE": "string"})
    assert frame["DATE"].tolist() == ["2024"]
    assert frame["STATION"].tolist() == ["USW00013967"]
    assert frame["PRCP"].tolist() == [900.0]
    assert frame.attrs["usdata"]["provenance"] == item.provenance.model_dump(mode="json")
    assert "units" not in frame.attrs
    assert item.path.read_bytes() == source
    assert verify(manifest, root=tmp_path / "cache") == []
