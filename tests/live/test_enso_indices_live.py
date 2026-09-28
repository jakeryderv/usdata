"""CPC's ENSO tables: fetch RONI and ONI, restore them, and read the first and a known season."""

from pathlib import Path

import pytest

from usdata.pull import pull, verify

pytestmark = pytest.mark.live

MANIFEST = """name: enso-indices
sources:
  - dataset: noaa:enso-indices
    name: roni
  - dataset: noaa:enso-indices
    name: oni
    params: {index: oni}
"""


def rows(path: Path) -> dict[tuple[str, int], list[str]]:
    lines = path.read_text().splitlines()
    return {(cells[0], int(cells[1])): cells[2:] for cells in (line.split() for line in lines[1:])}


def test_enso_tables_fetch_restore_and_hold_the_1997_peak(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    result = pull(manifest, root=tmp_path / "cache")
    roni, oni = result.one("roni"), result.one("oni")
    assert roni.path.read_text().split()[:3] == ["SEAS", "YR", "ANOM"]
    assert oni.path.read_text().split()[:4] == ["SEAS", "YR", "TOTAL", "ANOM"]
    assert ("DJF", 1950) in rows(roni.path) and ("DJF", 1950) in rows(oni.path)
    # NDJ 1997 was a very strong El Nino on both indices.
    assert float(rows(roni.path)[("NDJ", 1997)][-1]) > 2.0
    assert float(rows(oni.path)[("NDJ", 1997)][-1]) > 2.0
    roni.path.unlink()
    again = pull(manifest, root=tmp_path / "cache")
    assert again.from_lockfile and again.lockfile == result.lockfile
    assert verify(manifest, root=tmp_path / "cache") == []
