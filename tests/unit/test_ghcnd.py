from pathlib import Path

import httpx
import pytest
import respx

from usdata import provenance
from usdata.fetch import fetch, fetch_asset
from usdata.providers.base import QueryError
from usdata.providers.noaa.ghcnd import DATA_URL, SEARCH_URL, GhcnDaily
from usdata.query import build_query
from usdata.registry import default_registry

CSV = b'"DATE","STATION","TMAX"\n"2024-05-06","USW00013967","27.2"\n'


@pytest.fixture
def adapter() -> GhcnDaily:
    return GhcnDaily(default_registry().get("noaa:ghcn-daily"), client=httpx.Client())


def _search_page(stations: list[str], total: int) -> dict:
    return {
        "count": total,
        "totalCount": 132438,  # dataset-wide, must be ignored by pagination
        "results": [{"stations": [{"id": s, "name": s}]} for s in stations],
    }


def test_requires_dates_and_a_spatial_constraint(adapter: GhcnDaily) -> None:
    with pytest.raises(QueryError, match="start and end"):
        adapter.list_assets(build_query(location="ok"))
    with pytest.raises(QueryError, match="location"):
        adapter.list_assets(build_query(start="2024-05-06", end="2024-05-07"))


def test_explicit_stations_skip_search(adapter: GhcnDaily) -> None:
    q = build_query(start="2024-05-06", end="2024-05-07", stations="USW00013967, USW00003954")
    with respx.mock(assert_all_called=False) as mock:
        search = mock.get(SEARCH_URL)
        assets = adapter.list_assets(q)
    assert not search.called
    assert len(assets) == 1
    url = httpx.URL(assets[0].href)
    assert url.params["stations"] == "USW00013967,USW00003954"
    assert url.params["startDate"] == "2024-05-06"
    assert url.params["format"] == "csv"
    assert "dataTypes" not in url.params


def test_bbox_query_paginates_station_search(
    monkeypatch: pytest.MonkeyPatch, adapter: GhcnDaily
) -> None:
    monkeypatch.setattr("usdata.providers.noaa.ghcnd.SEARCH_PAGE_SIZE", 2)
    monkeypatch.setattr("usdata.providers.noaa.ghcnd.STATIONS_PER_ASSET", 2)
    q = build_query(location="ok", start="2024-05-06", end="2024-05-06", variables=["PRCP"])
    with respx.mock() as mock:
        route = mock.get(SEARCH_URL)
        route.side_effect = [
            httpx.Response(200, json=_search_page(["A", "B"], 3)),
            httpx.Response(200, json=_search_page(["B", "C"], 3)),
        ]
        assets = adapter.list_assets(q)
    assert route.call_count == 2
    first = route.calls[0].request.url.params
    assert q.bbox is not None
    assert float(first["bbox"].split(",")[0]) == q.bbox.north  # north first
    assert first["dataTypes"] == "PRCP"
    assert [httpx.URL(a.href).params["stations"] for a in assets] == ["A,B", "C"]
    assert all(httpx.URL(a.href).params["dataTypes"] == "PRCP" for a in assets)


def test_fetch_writes_file_and_provenance_then_uses_cache(
    tmp_path: Path, adapter: GhcnDaily, monkeypatch: pytest.MonkeyPatch
) -> None:
    ds = adapter.dataset
    q = build_query(start="2024-05-06", end="2024-05-06", stations=["USW00013967"])
    with respx.mock() as mock:
        data = mock.get(DATA_URL).mock(return_value=httpx.Response(200, content=CSV))
        first = fetch(ds, q, root=tmp_path)
        again = fetch(ds, q, root=tmp_path)
    assert data.call_count == 1
    (f,) = first
    assert f.path.read_bytes() == CSV
    assert f.path.is_relative_to(tmp_path / "noaa" / "ghcn-daily")
    assert not f.from_cache and again[0].from_cache
    assert provenance.read(f.path) == f.provenance == again[0].provenance
    assert f.provenance.source_url == f.asset.href
    assert f.provenance.size == len(CSV)


def test_fetch_http_error_leaves_no_partial_file(tmp_path: Path, adapter: GhcnDaily) -> None:
    q = build_query(start="2024-05-06", end="2024-05-06", stations=["X"])
    (asset,) = adapter.list_assets(q)
    with respx.mock() as mock:
        mock.get(DATA_URL).mock(return_value=httpx.Response(500))
        with pytest.raises(httpx.HTTPStatusError):
            adapter.fetch(asset, tmp_path / "out.csv")
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(httpx.HTTPStatusError), respx.mock() as mock:
        mock.get(DATA_URL).mock(return_value=httpx.Response(404))
        fetch_asset(adapter.dataset, asset, root=tmp_path)


@pytest.mark.parametrize(
    "params",
    [
        {"stations": "X", "untis": "standard"},
        {"stations": "X", "units": "kelvin"},
        {"stations": ""},
        {"stations": []},
        {"stations": 123},
        {"stations": [123]},
    ],
)
def test_rejects_invalid_provider_params(adapter: GhcnDaily, params: dict) -> None:
    with pytest.raises(QueryError):
        adapter.list_assets(build_query(start="2024-05-06", end="2024-05-07", **params))
