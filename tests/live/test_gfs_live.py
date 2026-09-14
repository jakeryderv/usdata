"""One GFS 1-degree analysis file: resolve with sizes, fetch, restore, and open CAPE."""

from importlib.util import find_spec
from typing import Any

import pytest

from usdata import build_query, get
from usdata.fetch import FetchedAsset
from usdata.providers import load_adapter
from usdata.pull import pull, verify

pytestmark = pytest.mark.live

MANIFEST = """name: gfs-analysis
sources:
  - dataset: noaa:gfs
    start: 2024-05-06T00:00:00Z
    end: 2024-05-06T00:00:00Z
    params: {cycle: 0, forecast_hour: 0, resolution: 1p00}
"""
SIZE = 42_362_644


@pytest.fixture(scope="module")
def restored(tmp_path_factory: pytest.TempPathFactory) -> FetchedAsset:
    """The 42 MB analysis, fetched once per module, then restored through its lockfile."""
    root = tmp_path_factory.mktemp("gfs")
    manifest = root / "dataset.yaml"
    manifest.write_text(MANIFEST)
    result = pull(manifest, root=root / "cache")
    (item,) = result.fetched
    assert item.asset.id == "gfs.20240506.t00z.pgrb2.1p00.f000"
    assert item.path.stat().st_size == SIZE
    with item.path.open("rb") as stream:
        assert stream.read(4) == b"GRIB"
    item.path.unlink()
    again = pull(manifest, root=root / "cache")
    assert again.from_lockfile and again.lockfile == result.lockfile
    assert again.fetched[0].provenance.checksum == item.provenance.checksum
    assert verify(manifest, root=root / "cache") == []
    return again.fetched[0]


def test_gfs_listing_reports_sizes_before_download() -> None:
    with load_adapter(get("noaa:gfs")) as adapter:
        listed = adapter.list_assets(
            build_query(
                start="2024-05-06T00:00Z",
                end="2024-05-06T00:00Z",
                cycle=0,
                forecast_hour="0,3",
                resolution="1p00",
            )
        )
    assert [asset.id for asset in listed] == [
        "gfs.20240506.t00z.pgrb2.1p00.f000",
        "gfs.20240506.t00z.pgrb2.1p00.f003",
    ]
    assert [asset.size for asset in listed] == [SIZE, 44_925_309]


def test_gfs_analysis_fetches_and_restores(restored: FetchedAsset) -> None:
    assert not restored.from_cache
    assert restored.path.stat().st_size == SIZE


def test_gfs_surface_cape_opens_with_grib_reader(restored: FetchedAsset) -> None:
    if find_spec("eccodes") is None or find_spec("xarray") is None:
        pytest.skip("grib extra not installed")
    options: dict[str, Any] = {"select": {"shortName": "cape", "typeOfLevel": "surface"}}
    fields = restored.open(**options)
    (name,) = list(fields.data_vars)
    assert fields[name].shape == (181, 360)
    assert fields[name].attrs["units"].replace("**", "").replace(" ", "") in {"Jkg-1", "J/kg"}
    assert float(fields.latitude.max()) == 90.0 and float(fields.longitude.max()) == 359.0
