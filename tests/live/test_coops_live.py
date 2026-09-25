"""Three-day historical CO-OPS request, original quality fields, and pinned restoration."""

import csv
from importlib.util import find_spec
from pathlib import Path

import pytest

from usdata.pull import pull, verify

pytestmark = pytest.mark.live


def test_coops_water_levels_restore(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    example = (
        Path(__file__).resolve().parents[2]
        / "examples/datasets/noaa-coops-water-levels/dataset.yaml"
    )
    manifest.write_bytes(example.read_bytes())
    result = pull(manifest, root=tmp_path / "cache")
    (item,) = result.fetched
    with item.path.open(newline="") as stream:
        rows = [
            {name.strip(): value for name, value in row.items()} for row in csv.DictReader(stream)
        ]
    assert len(rows) == 720  # three whole days of six-minute readings
    assert {row["Quality"].strip() for row in rows} == {"v"}
    assert rows[0]["Date Time"] == "2024-05-06 00:00"
    assert rows[-1]["Date Time"] == "2024-05-08 23:54"
    assert all(-10 < float(row["Water Level"]) < 10 for row in rows)
    original = item.path.read_bytes()
    item.path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and not restored.fetched[0].from_cache
    assert restored.fetched[0].path.read_bytes() == original
    assert restored.lockfile == result.lockfile
    assert verify(manifest, root=tmp_path / "cache") == []
    if find_spec("pandas") is not None:
        frame = restored.fetched[0].open_csv(parse_dates=["Date Time"])
        assert len(frame) == 720
        assert " Quality " in frame.columns
        assert frame.attrs["usdata"]["provenance"]["checksum"] == item.provenance.checksum
