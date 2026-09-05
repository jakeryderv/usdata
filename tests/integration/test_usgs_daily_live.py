"""Small live USGS daily-values query, including pagination and locked restoration."""

import csv
from pathlib import Path

import pytest

from usdata.pull import pull, verify

pytestmark = pytest.mark.integration


def test_tulsa_daily_streamflow(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("usdata.providers.usgs.daily.PAGE_SIZE", 1)
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: tulsa-streamflow
sources:
  - dataset: usgs:water-daily
    start: 2024-05-06
    end: 2024-05-07
    variables: ['00060']
    params: {sites: '07164500'}
""")
    result = pull(manifest, root=tmp_path / "cache")
    rows = []
    for item in result.fetched:
        with item.path.open(newline="") as f:
            rows.extend(csv.DictReader(f))
    assert len(rows) == 2
    assert {r["time"] for r in rows} == {"2024-05-06", "2024-05-07"}
    assert all(r["monitoring_location_id"] == "USGS-07164500" for r in rows)
    assert all(r["parameter_code"] == "00060" and r["unit_of_measure"] == "ft^3/s" for r in rows)
    assert all(r["approval_status"] and float(r["value"]) > 0 for r in rows)
    result.fetched[0].path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and not restored.fetched[0].from_cache
    assert verify(manifest, root=tmp_path / "cache") == []


def test_documented_noaa_usgs_example(tmp_path: Path) -> None:
    example = Path(__file__).resolve().parents[2] / "examples/weather-and-streamflow/dataset.yaml"
    manifest = tmp_path / "dataset.yaml"
    manifest.write_bytes(example.read_bytes())
    first = pull(manifest, root=tmp_path / "cache")
    assert len(first.fetched) == 2
    assert {item.asset.dataset_id for item in first.fetched} == {
        "noaa:ghcn-daily",
        "usgs:water-daily",
    }
    assert verify(manifest, root=tmp_path / "cache") == []
    again = pull(manifest, root=tmp_path / "cache")
    assert all(item.from_cache for item in again.fetched)
    first.fetched[0].path.unlink()
    assert not pull(manifest, root=tmp_path / "cache").fetched[0].from_cache
