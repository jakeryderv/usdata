"""Small live ComCat query, pinned and restored, opened with pandas when it is installed."""

import csv
from pathlib import Path

import pytest

from usdata.pull import pull, verify

pytestmark = pytest.mark.live


def test_oklahoma_events_on_the_tornado_days(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: oklahoma-earthquakes
sources:
  - dataset: usgs:earthquakes
    location: Oklahoma
    start: 2024-05-06
    end: 2024-05-07
    params: {min_magnitude: 1.0}
""")
    result = pull(manifest, root=tmp_path / "cache")
    (item,) = result.fetched
    with item.path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows and all(float(r["mag"]) >= 1.0 for r in rows)
    assert all(r["time"].startswith(("2024-05-06", "2024-05-07")) for r in rows)
    assert all(33.5 <= float(r["latitude"]) <= 37.1 for r in rows)
    assert rows == sorted(rows, key=lambda r: r["time"])
    item.path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and not restored.fetched[0].from_cache
    assert verify(manifest, root=tmp_path / "cache") == []
    pandas = pytest.importorskip("pandas")
    frame = restored.fetched[0].open()
    assert isinstance(frame, pandas.DataFrame) and len(frame) == len(rows)
