"""Bounded GSOY checks: one airport, one year, exact CSV restoration."""

import csv
import logging
from pathlib import Path

import pytest

from usdata.providers.noaa.gsoy import GlobalSummaryYearly
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.live


def test_gsoy_station_discovery(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="usdata.providers.noaa.ghcnd")
    query = build_query(
        bbox=(-97.62, 35.38, -97.58, 35.40),
        start="2024-05-06",
        end="2024-05-07",
        variables=["PRCP", "TAVG"],
    )
    with GlobalSummaryYearly(default_registry().get("noaa:gsoy")) as adapter:
        stations = adapter.find_stations(query)
    assert "USW00013967" in stations, f"GSOY search did not find OKC airport: {stations}"


def test_gsoy_annual_example_restore(tmp_path: Path) -> None:
    example = Path(__file__).resolve().parents[2] / "examples/annual-climate/dataset.yaml"
    manifest = tmp_path / "dataset.yaml"
    manifest.write_bytes(example.read_bytes())
    result = pull(manifest, root=tmp_path / "cache")
    (item,) = result.fetched
    with item.path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1 and rows[0]["DATE"] == "2024"
    assert rows[0]["STATION"] == "USW00013967"
    assert float(rows[0]["PRCP"]) >= 0 and -60 < float(rows[0]["TAVG"]) < 60
    original = item.path.read_bytes()
    item.path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and not restored.fetched[0].from_cache
    assert restored.fetched[0].path.read_bytes() == original
    assert restored.lockfile == result.lockfile
    assert verify(manifest, root=tmp_path / "cache") == []
