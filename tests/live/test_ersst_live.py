"""ERSST v6: list the first and a recent month, fetch one, restore it, and open it."""

from importlib.util import find_spec
from pathlib import Path

import pytest

from usdata import build_query, get
from usdata.providers import load_adapter
from usdata.pull import pull, verify

pytestmark = pytest.mark.live

MANIFEST = """name: ersst-december-1997
sources:
  - dataset: noaa:ersst
    start: 1997-12-01
    end: 1997-12-31
"""


def test_ersst_listing_reaches_back_to_1850_with_sizes() -> None:
    with load_adapter(get("noaa:ersst")) as adapter:
        first = adapter.list_assets(build_query(start="1850-01-01", end="1850-02-28"))
    assert [asset.id for asset in first] == ["ersst.v6.185001.nc", "ersst.v6.185002.nc"]
    assert all(asset.size and asset.size > 100_000 for asset in first)


def test_ersst_month_fetches_restores_and_opens(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    result = pull(manifest, root=tmp_path / "cache")
    (item,) = result.fetched
    assert item.asset.id == "ersst.v6.199712.nc"
    assert item.path.read_bytes()[:4] == b"\x89HDF"
    item.path.unlink()
    again = pull(manifest, root=tmp_path / "cache")
    assert again.from_lockfile and again.lockfile == result.lockfile
    assert verify(manifest, root=tmp_path / "cache") == []
    if find_spec("xarray") is None or find_spec("h5netcdf") is None:
        pytest.skip("netcdf extra not installed")
    grid = again.fetched[0].open()
    assert dict(grid.sizes) == {"time": 1, "lev": 1, "lat": 89, "lon": 180}
    assert grid.sst.attrs["units"] == "degree_C"
    # December 1997 was the peak of a very strong El Nino: Nino 3.4 well above +2 degrees.
    nino34 = float(grid.ssta.sel(lat=slice(-5, 5), lon=slice(190, 240)).mean())
    assert 2.0 < nino34 < 3.0
