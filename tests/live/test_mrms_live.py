"""One two-minute MRMS rotation-track file, with checksum-locked restoration."""

import gzip
from importlib.util import find_spec
from pathlib import Path

import pytest

from usdata.pull import pull, verify

pytestmark = pytest.mark.live

MANIFEST = """name: one-mrms-file
sources:
  - dataset: noaa:mrms
    start: 2024-05-06T20:00:00Z
    end: 2024-05-06T20:00:00Z
    params: {product: RotationTrackML30min_00.50}
"""


def test_rotation_track_file_restore(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    result = pull(manifest, root=tmp_path / "cache")
    (item,) = result.fetched
    assert item.asset.id == "MRMS_RotationTrackML30min_00.50_20240506-200000.grib2.gz"
    assert item.asset.media_type == "application/x-grib2"
    assert item.asset.time is not None and item.asset.time.start is not None
    assert item.asset.time.start.isoformat() == "2024-05-06T20:00:00+00:00"
    assert item.path.stat().st_size == item.asset.size
    with gzip.open(item.path, "rb") as stream:
        assert stream.read(4) == b"GRIB"
    item.path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and not restored.fetched[0].from_cache
    assert restored.lockfile == result.lockfile
    assert verify(manifest, root=tmp_path / "cache") == []
    if find_spec("eccodes") is None or find_spec("xarray") is None:
        return
    try:
        grid = restored.fetched[0].open()
    except ValueError as error:  # The grib reader is a separate change in this release.
        pytest.skip(f"grib reader unavailable: {error}")
    (name,) = list(grid.data_vars)
    assert grid[name].shape == (7000, 14000)
    assert float(grid[name].max()) >= 0
