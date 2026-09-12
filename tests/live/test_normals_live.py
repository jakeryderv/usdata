"""Bounded normals checks: one airport, monthly and daily windows, exact restoration."""

import csv
from pathlib import Path

import pytest

from usdata.providers.noaa.normals import ClimateNormals
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.live


def test_normals_station_discovery() -> None:
    query = build_query(bbox=(-97.62, 35.38, -97.58, 35.40), period="monthly")
    with ClimateNormals(default_registry().get("noaa:climate-normals")) as adapter:
        stations = adapter.find_stations(query)
    assert "USW00013967" in stations, f"normals search did not find OKC airport: {stations}"


def test_daily_window_ignores_the_year(tmp_path: Path) -> None:
    dataset = default_registry().get("noaa:climate-normals")
    query = build_query(
        start="2024-02-27",
        end="2024-03-01",
        stations="USW00013967",
        period="daily",
        variables=["DLY-TMAX-NORMAL"],
    )
    with ClimateNormals(dataset) as adapter:
        (asset,) = adapter.list_assets(query)
        path = adapter.fetch(asset, tmp_path / "daily.csv")
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [r["DATE"] for r in rows] == ["02-27", "02-28", "02-29", "03-01"]


def test_monthly_example_restore(tmp_path: Path) -> None:
    example = Path(__file__).resolve().parents[2] / "examples/climate-normals/dataset.yaml"
    manifest = tmp_path / "dataset.yaml"
    manifest.write_bytes(example.read_bytes())
    result = pull(manifest, root=tmp_path / "cache")
    (item,) = result.fetched
    with item.path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [r["DATE"] for r in rows] == [f"{m:02d}" for m in range(1, 13)]
    assert all(-30 < float(r["MLY-TMAX-NORMAL"].strip()) < 50 for r in rows)
    original = item.path.read_bytes()
    item.path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and not restored.fetched[0].from_cache
    assert restored.fetched[0].path.read_bytes() == original
    assert verify(manifest, root=tmp_path / "cache") == []
