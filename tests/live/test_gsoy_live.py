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
    example = Path(__file__).resolve().parents[2] / "examples/datasets/noaa-gsoy/dataset.yaml"
    manifest = tmp_path / "dataset.yaml"
    manifest.write_bytes(example.read_bytes())
    result = pull(manifest, root=tmp_path / "cache")
    (item,) = result.fetched
    with item.path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    # The walkthrough's thirty full years, 1995 to 2024, one row each.
    assert [row["DATE"] for row in rows] == [str(year) for year in range(1995, 2025)]
    assert {row["STATION"] for row in rows} == {"USW00013967"}
    assert all(float(row["PRCP"]) >= 0 and -60 < float(row["TAVG"]) < 60 for row in rows)
    original = item.path.read_bytes()
    item.path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and not restored.fetched[0].from_cache
    assert restored.fetched[0].path.read_bytes() == original
    assert restored.lockfile == result.lockfile
    assert verify(manifest, root=tmp_path / "cache") == []
