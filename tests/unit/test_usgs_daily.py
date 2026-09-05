from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata import build_query, get
from usdata.cli import app
from usdata.fetch import fetch
from usdata.providers.base import QueryError
from usdata.providers.noaa.ghcnd import DATA_URL as NOAA_DATA_URL
from usdata.providers.usgs.daily import ITEMS_URL, WaterDaily
from usdata.pull import pull, verify

CSV = b"time,monitoring_location_id,parameter_code,value\n2024-05-06,USGS-07164500,00060,12300\n"


def page(ids: list[str], next_url: str | None = None) -> dict:
    return {
        "features": [{"id": id} for id in ids],
        "links": [{"rel": "next", "href": next_url}] if next_url else [],
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"start": "2024-01-01", "end": "2024-01-02"},
        {"site": "wrong"},
        {"sites": 12345},
        {"sites": []},
        {"site": "07164500", "variables": ["PRCP"]},
        {"site": "07164500", "statistic_id": 3},
        {"site": "07164500", "sites": "07164500"},
        {"site": "07164500", "typo": True},
    ],
)
def test_bad_queries_fail_before_network(kwargs: dict) -> None:
    defaults = {} if not kwargs else {"start": "2024-01-01", "end": "2024-01-02"}
    query = build_query(**{**defaults, **kwargs})
    with WaterDaily(get("usgs:water-daily")) as adapter, pytest.raises(QueryError):
        adapter.list_assets(query)


def test_pagination_keeps_filters_and_avoids_cursor_fallback_duplicates(monkeypatch) -> None:
    monkeypatch.setattr("usdata.providers.usgs.daily.PAGE_SIZE", 1)
    q = build_query(start="2024-05-06", end="2024-05-07", sites="07164500", variables=["00060"])
    with respx.mock() as mock, WaterDaily(get("usgs:water-daily")) as adapter:
        route = mock.get(ITEMS_URL).mock(
            side_effect=[
                httpx.Response(200, json=page(["a"], ITEMS_URL + "?cursor=a")),
                httpx.Response(200, json=page(["b"], ITEMS_URL + "?offset=1")),
                httpx.Response(200, json=page([])),
            ]
        )
        assets = adapter.list_assets(q)
    assert len(assets) == 2
    assert [c.request.url.params["offset"] for c in route.calls] == ["0", "1", "2"]
    for call in route.calls:
        params = call.request.url.params
        assert params["time"] == "2024-05-06/2024-05-07"
        assert params["monitoring_location_id"] == "USGS-07164500"
        assert params["parameter_code"] == "00060"
        assert params["statistic_id"] == "00003"
        assert "sortby" not in params and "cursor" not in params
    assert all(httpx.URL(a.href).params["f"] == "csv" for a in assets)
    assert len({a.id for a in assets}) == 2


def test_bbox_variables_and_sites_normalize_deterministically() -> None:
    kwargs: dict = dict(start="2024-05-06", end="2024-05-07", bbox=(-96.01, 36.13, -96, 36.15))
    with respx.mock() as mock, WaterDaily(get("usgs:water-daily")) as adapter:
        route = mock.get(ITEMS_URL).respond(200, json=page(["a"]))
        a = adapter.list_assets(
            build_query(**kwargs, sites="USGS-07164500,07164500", variables=["00060", "00065"])
        )
        b = adapter.list_assets(
            build_query(**kwargs, sites=["07164500"], variables=["00065", "00060"])
        )
    assert [x.id for x in a] == [x.id for x in b]
    assert route.call_count == 4
    assert route.calls[0].request.url.params["bbox"] == "-96.01,36.13,-96.0,36.15"


def test_empty_results_and_upstream_failure(tmp_path: Path) -> None:
    q = build_query(start="2024-05-06", end="2024-05-07", location="OK")
    with respx.mock() as mock:
        mock.get(ITEMS_URL).respond(200, json=page([]))
        assert fetch(get("usgs:water-daily"), q, root=tmp_path) == []
    with respx.mock() as mock:
        mock.get(ITEMS_URL).respond(503)
        with pytest.raises(httpx.HTTPStatusError):
            fetch(get("usgs:water-daily"), q, root=tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("include_noaa", [False, True])
def test_manifest_restores_csv_without_listing(tmp_path: Path, include_noaa: bool) -> None:
    m = tmp_path / "dataset.yaml"
    m.write_text("""name: streamflow
sources:
  - dataset: usgs:water-daily
    start: 2024-05-06
    end: 2024-05-07
    variables: ['00060']
    params: {sites: '07164500'}
""")
    if include_noaa:
        m.write_text(
            m.read_text()
            + """  - dataset: noaa:ghcn-daily
    start: 2024-05-06
    end: 2024-05-07
    params: {stations: USW00013967}
"""
        )
    with respx.mock() as mock:
        listing = mock.get(ITEMS_URL, params={"f": "json"}).respond(200, json=page(["a"]))
        data = mock.get(ITEMS_URL, params={"f": "csv"}).respond(200, content=CSV)
        if include_noaa:
            mock.get(NOAA_DATA_URL).respond(200, content=b"NOAA observations")
        result = pull(m, root=tmp_path / "cache")
        assert len(result.fetched) == (2 if include_noaa else 1)
        assert listing.call_count == data.call_count == 1
    item = result.fetched[0]
    assert item.path.read_bytes() == CSV
    assert item.provenance.source_url == item.asset.href
    item.path.unlink()
    with respx.mock() as mock:
        mock.get(item.asset.href).respond(200, content=CSV)
        restored = pull(m, root=tmp_path / "cache")
    assert restored.from_lockfile
    assert verify(m, root=tmp_path / "cache") == []


def test_cli_dry_run_and_borrowed_client() -> None:
    with respx.mock() as mock:
        mock.get(ITEMS_URL).respond(200, json=page(["a"]))
        result = CliRunner().invoke(
            app,
            [
                "fetch",
                "usgs:water-daily",
                "-p",
                "sites=07164500",
                "--start",
                "2024-05-06",
                "--end",
                "2024-05-07",
                "--vars",
                "00060",
                "--dry-run",
            ],
        )
    assert result.exit_code == 0 and "f=csv" in result.stdout
    with httpx.Client() as client:
        with WaterDaily(get("usgs:water-daily"), client=client):
            pass
        assert not client.is_closed
