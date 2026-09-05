"""Tiny live CoastWatch subset, including restored bytes and scientific columns."""

import csv
from pathlib import Path

import pytest

from usdata.pull import pull, verify

pytestmark = pytest.mark.integration


def test_coastwatch_subset_and_locked_restoration(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: coastwatch-small
sources:
  - dataset: noaa:coastwatch-sst
    bbox: {west: -80.08, south: 30.02, east: -80.02, north: 30.08}
    start: 2024-05-06T12:00:00Z
    end: 2024-05-06T12:00:00Z
    variables: [analysed_sst, analysis_error]
""")
    first = pull(manifest, root=tmp_path / "cache")
    assert len(first.fetched) == 1
    with first.fetched[0].path.open(newline="") as file:
        reader = csv.DictReader(file)
        units = next(reader)
        rows = list(reader)
    assert units["analysed_sst"] == units["analysis_error"] == "degree_C"
    assert len(rows) == 4
    assert {r["time"] for r in rows} == {"2024-05-06T12:00:00Z"}
    assert all(30.02 <= float(r["latitude"]) <= 30.08 for r in rows)
    assert all(-80.08 <= float(r["longitude"]) <= -80.02 for r in rows)
    assert all(20 < float(r["analysed_sst"]) < 35 for r in rows)
    assert all(float(r["analysis_error"]) >= 0 for r in rows)
    assert pull(manifest, root=tmp_path / "cache").fetched[0].from_cache
    first.fetched[0].path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert not restored.fetched[0].from_cache
    assert restored.fetched[0].provenance.checksum == first.fetched[0].provenance.checksum
    assert verify(manifest, root=tmp_path / "cache") == []
