"""Twelve minutes of observed currents and byte-for-byte pinned restoration."""

import csv
from importlib.util import find_spec
from pathlib import Path

import pytest

from usdata import pull, verify

pytestmark = pytest.mark.live


def test_coops_currents_restore(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(
        "name: current-probe\nsources:\n"
        "  - name: currents\n    dataset: noaa:coops-currents\n"
        "    start: 2025-05-06T00:02Z\n    end: 2025-05-06T00:14Z\n"
        "    params: {station: cb0102, bin: 4, units: metric}\n"
    )
    result = pull(manifest, root=tmp_path / "cache")
    item = result.one("currents")
    rows = list(csv.DictReader(item.path.read_text().splitlines(), skipinitialspace=True))
    rows = [{key.strip(): value.strip() for key, value in row.items()} for row in rows]
    assert len(rows) == 3 and {row["Bin"] for row in rows} == {"4"}
    assert rows[0]["Date Time"] == "2025-05-06 00:02"
    assert all(0 <= float(row["Speed"]) < 1000 for row in rows)
    assert all(0 <= float(row["Direction"]) <= 360 for row in rows)
    restored = pull(manifest, root=tmp_path / "restored")
    copy = restored.one("currents")
    assert restored.from_lockfile and not copy.from_cache
    assert restored.lockfile == result.lockfile
    assert copy.path.read_bytes() == item.path.read_bytes()
    assert verify(manifest, root=tmp_path / "restored") == []
    if find_spec("pandas") is not None:
        frame = copy.open()
        assert len(frame) == 3 and " Bin " in frame.columns
        assert frame.attrs["usdata"]["provenance"]["checksum"] == item.provenance.checksum
