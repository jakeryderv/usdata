"""GSOM station files: fetch two stations whole, restore them, and match the service's values."""

from pathlib import Path

import pytest

from usdata.pull import pull, verify

pytestmark = pytest.mark.live

MANIFEST = """name: gsom-station-files
sources:
  - dataset: noaa:gsom-station-files
    params: {stations: [USW00094823, USC00100667]}
"""


def test_station_files_fetch_restore_and_hold_pittsburghs_1997_winter(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    result = pull(manifest, root=tmp_path / "cache")
    by_id = {item.asset.id: item for item in result.fetched}
    assert set(by_id) == {"USW00094823.csv", "USC00100667.csv"}
    pittsburgh, other = by_id["USW00094823.csv"], by_id["USC00100667.csv"]
    pytest.importorskip("pandas")
    frame = pittsburgh.open()
    assert frame.attrs["usdata"]["properties"] == {"units": "metric"}
    winter = frame.set_index("DATE").loc["1997-11":"1998-03", "SNOW"].tolist()
    # The Access Data Service returns the same five months under units=metric.
    assert winter == [64, 320, 45, 64, 125]
    other.path.unlink()
    again = pull(manifest, root=tmp_path / "cache")
    assert again.from_lockfile and again.lockfile == result.lockfile
    assert verify(manifest, root=tmp_path / "cache") == []
