"""Bounded live check: the 2024 SPC tornado file (about 230 KB), its schema, and restoration."""

import csv
from importlib.util import find_spec
from pathlib import Path

import pytest

from usdata.cache import sha256_file
from usdata.pull import pull, verify

pytestmark = pytest.mark.live

MANIFEST = """name: tornadoes-2024
sources:
  - dataset: noaa:spc-tornado-reports
    start: 2024-01-01
    end: 2024-12-31
"""


def test_annual_file_schema_ratings_and_locked_restore(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    result = pull(manifest, root=tmp_path / "cache")
    (item,) = result.fetched
    assert item.asset.id == "2024_torn.csv"
    assert item.provenance.checksum == sha256_file(item.path)
    with item.path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert 1000 < len(rows) < 5000
    expected = {"om", "yr", "date", "time", "tz", "st", "mag", "slat", "slon", "len", "wid", "sg"}
    assert expected <= rows[0].keys()
    assert all(row["yr"] == "2024" for row in rows)
    assert all(len(row["st"]) == 2 and row["st"].isalpha() for row in rows)
    assert {int(row["mag"]) for row in rows} <= {-9, 0, 1, 2, 3, 4, 5}
    assert all(row["tz"] == "3" for row in rows)
    tracks = [row for row in rows if row["sg"] == "1"]
    assert 0.9 * len(rows) < len(tracks) <= len(rows)
    original = item.path.read_bytes()
    item.path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and restored.fetched[0].path.read_bytes() == original
    assert verify(manifest, root=tmp_path / "cache") == []
    if find_spec("pandas") is not None:
        frame = restored.fetched[0].open(parse_dates=["date"])
        assert len(frame) == len(rows) and frame["mag"].between(-9, 5).all()


def test_the_hail_table_reports_stone_sizes_in_inches(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(
        MANIFEST.replace(
            "    end: 2024-12-31\n", "    end: 2024-12-31\n    params: {table: hail}\n"
        )
    )
    (item,) = pull(manifest, root=tmp_path / "cache").fetched
    assert item.asset.id == "2024_hail.csv"
    with item.path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    sizes = [float(row["mag"]) for row in rows]
    # Inches, not an F scale and not knots: nothing negative, nothing the size of a wind speed.
    assert len(rows) > 1000 and all(0 < size < 10 for size in sizes)
    assert "fc" not in rows[0] and "mt" not in rows[0]
    assert verify(manifest, root=tmp_path / "cache") == []
