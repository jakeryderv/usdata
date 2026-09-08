from pathlib import Path

import httpx
import pytest
import respx

from usdata import provenance
from usdata.fetch import ChecksumMismatch, fetch
from usdata.providers.base import QueryError
from usdata.providers.noaa.ghcnd import DATA_URL, SEARCH_URL
from usdata.providers.noaa.gsom import GlobalSummaryMonthly
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

CSV = b'"STATION","DATE","PRCP","TAVG"\n"USW00013967","2024-05","91.8","21.7"\n'
MANIFEST = """name: monthly-climate
sources:
  - dataset: noaa:gsom
    start: 2024-05-06
    end: 2024-05-07
    variables: [PRCP, TAVG]
    params: {stations: USW00013967, units: metric}
"""


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield GlobalSummaryMonthly(default_registry().get("noaa:gsom"), client=client)


@pytest.mark.parametrize(
    ("start", "end", "expected_start", "expected_end"),
    [
        ("2024-05-06", "2024-05-07", "2024-05-01", "2024-05-31"),
        ("2024-02-29", "2024-02-29", "2024-02-01", "2024-02-29"),
        ("2023-12-31", "2024-01-01", "2023-12-01", "2024-01-31"),
        ("2024-06-01T00:30+02:00", "2024-06-01T00:30+02:00", "2024-05-01", "2024-05-31"),
    ],
)
def test_whole_month_urls_and_asset_coverage(
    adapter, start: str, end: str, expected_start: str, expected_end: str
) -> None:
    query = build_query(start=start, end=end, stations="USW00013967", variables=["PRCP"])
    with respx.mock() as mock:
        (asset,) = adapter.list_assets(query)
        assert not mock.calls
    params = httpx.URL(asset.href).params
    assert params["dataset"] == "global-summary-of-the-month"
    assert params["startDate"] == expected_start and params["endDate"] == expected_end
    assert params["units"] == "metric" and params["dataTypes"] == "PRCP"
    assert params["includeStationLocation"] == "1"
    assert asset.dataset_id == "noaa:gsom" and asset.media_type == "text/csv"
    assert asset.time.start.isoformat() == expected_start + "T00:00:00+00:00"
    assert asset.time.end.isoformat() == expected_end + "T23:59:59.999999+00:00"
    normalized = build_query(
        start=expected_start, end=expected_end, stations="USW00013967", variables=["PRCP"]
    )
    assert adapter.list_assets(normalized)[0] == asset


def test_search_uses_month_bounds_paginates_and_deduplicates(adapter, monkeypatch) -> None:
    monkeypatch.setattr("usdata.providers.noaa.ghcnd.SEARCH_PAGE_SIZE", 2)
    monkeypatch.setattr("usdata.providers.noaa.ghcnd.STATIONS_PER_ASSET", 2)
    query = build_query(
        bbox=(-97.62, 35.38, -97.58, 35.40),
        start="2024-05-06",
        end="2024-05-07",
        variables=["PRCP", "TAVG"],
        units="standard",
    )
    with respx.mock() as mock:
        route = mock.get(SEARCH_URL)
        route.side_effect = [
            httpx.Response(
                200,
                json={
                    "count": 3,
                    "totalCount": 127947,
                    "results": [{"stations": [{"id": sid}]} for sid in station_ids],
                },
            )
            for station_ids in [["A", "B"], ["B", "C"]]
        ]
        assets = adapter.list_assets(query)
    assert route.call_count == 2
    for call, offset in zip(route.calls, ("0", "2"), strict=True):
        params = call.request.url.params
        assert params["dataset"] == "global-summary-of-the-month"
        assert params["startDate"] == "2024-05-01" and params["endDate"] == "2024-05-31"
        assert params["bbox"] == "35.4,-97.62,35.38,-97.58" and params["offset"] == offset
        assert params["dataTypes"] == "PRCP,TAVG"
    assert [httpx.URL(asset.href).params["stations"] for asset in assets] == ["A,B", "C"]
    assert all(httpx.URL(asset.href).params["units"] == "standard" for asset in assets)


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"start": "2024-05-01"},
        {"end": "2024-05-31"},
        {"start": "2024-05-01", "end": "2024-05-31"},
        {"stations": ""},
        {"stations": []},
        {"stations": [123]},
        {"stations": "X", "units": "kelvin"},
        {"stations": "X", "untis": "metric"},
        {"stations": "X", "location": "ok"},
    ],
)
def test_invalid_queries_fail_before_network(adapter, kwargs) -> None:
    if "stations" in kwargs:
        kwargs = {"start": "2024-05-01", "end": "2024-05-31", **kwargs}
    with respx.mock() as mock, pytest.raises(QueryError):
        adapter.list_assets(build_query(**kwargs))
    assert not mock.calls


def test_no_matching_stations_is_empty(adapter) -> None:
    with respx.mock() as mock:
        mock.get(SEARCH_URL).respond(200, json={"count": 0, "results": []})
        assert (
            adapter.list_assets(build_query(location="ok", start="2024-05-01", end="2024-05-31"))
            == []
        )


def test_fetch_cache_retains_bytes_and_provenance(tmp_path: Path) -> None:
    dataset = default_registry().get("noaa:gsom")
    query = build_query(start="2024-05-06", end="2024-05-07", stations="USW00013967")
    with respx.mock() as mock:
        route = mock.get(DATA_URL).respond(200, content=CSV)
        (item,) = fetch(dataset, query, root=tmp_path)
        (cached,) = fetch(dataset, query, root=tmp_path)
    assert route.call_count == 1 and cached.from_cache
    assert item.path.read_bytes() == CSV and item.path.is_relative_to(tmp_path / "noaa/gsom")
    assert provenance.read(item.path) == item.provenance
    assert query.time is not None and query.time.start is not None
    assert query.time.start.isoformat() == "2024-05-06T00:00:00+00:00"
    assert item.provenance.source_url == item.asset.href


def test_locked_restore_reuses_url_and_rejects_revised_bytes(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    with respx.mock() as mock:
        data = mock.get(DATA_URL).respond(200, content=CSV)
        first = pull(manifest, root=tmp_path / "cache")
        first.fetched[0].path.unlink()
        restored = pull(manifest, root=tmp_path / "cache")
    assert data.call_count == 2 and restored.from_lockfile
    assert data.calls[0].request.url == data.calls[1].request.url
    assert first.lockfile == restored.lockfile
    assert verify(manifest, root=tmp_path / "cache") == []
    first.fetched[0].path.unlink()
    with respx.mock() as mock, pytest.raises(ChecksumMismatch):
        mock.get(DATA_URL).respond(200, content=CSV.replace(b"91.8", b"91.9"))
        pull(manifest, root=tmp_path / "cache")


def test_open_monthly_csv_preserves_identifiers_and_metadata(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(200, content=CSV)
        (item,) = pull(manifest, root=tmp_path / "cache").fetched
    frame = item.open()
    assert str(frame["STATION"].dtype) == "string"
    assert frame["DATE"].tolist() == ["2024-05"]
    assert frame["PRCP"].tolist() == [91.8]
    assert frame.attrs["usdata"]["provenance"] == item.provenance.model_dump(mode="json")
    assert "units" not in frame.attrs  # NCEI CSV has no units row.
    assert item.path.read_bytes() == CSV
