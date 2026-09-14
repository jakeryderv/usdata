"""One HRRR surface analysis file: resolve with sizes, fetch, restore, and open CAPE."""

from importlib.util import find_spec
from typing import Any

import pytest

from usdata import build_query, get
from usdata.fetch import FetchedAsset
from usdata.providers import load_adapter
from usdata.pull import pull, verify

pytestmark = pytest.mark.live

MANIFEST = """name: hrrr-analysis
sources:
  - dataset: noaa:hrrr
    start: 2024-05-06T20:00:00Z
    end: 2024-05-06T20:00:00Z
    params: {cycle: 20, forecast_hour: 0}
"""


@pytest.fixture(scope="module")
def restored(tmp_path_factory: pytest.TempPathFactory) -> FetchedAsset:
    """The 150 MB analysis, fetched once per module, then restored through its lockfile."""
    root = tmp_path_factory.mktemp("hrrr")
    manifest = root / "dataset.yaml"
    manifest.write_text(MANIFEST)
    result = pull(manifest, root=root / "cache")
    (item,) = result.fetched
    assert item.asset.id == "hrrr.20240506.t20z.wrfsfcf00.grib2"
    assert item.path.stat().st_size == 150_114_757
    with item.path.open("rb") as stream:
        assert stream.read(4) == b"GRIB"
    item.path.unlink()
    again = pull(manifest, root=root / "cache")
    assert again.from_lockfile and again.lockfile == result.lockfile
    assert again.fetched[0].provenance.checksum == item.provenance.checksum
    assert verify(manifest, root=root / "cache") == []
    return again.fetched[0]


def test_hrrr_listing_reports_sizes_before_download() -> None:
    with load_adapter(get("noaa:hrrr")) as adapter:
        listed = adapter.list_assets(
            build_query(
                start="2024-05-06T20:00Z", end="2024-05-06T20:00Z", cycle=20, forecast_hour="0,1"
            )
        )
    assert [asset.id for asset in listed] == [
        "hrrr.20240506.t20z.wrfsfcf00.grib2",
        "hrrr.20240506.t20z.wrfsfcf01.grib2",
    ]
    assert [asset.size for asset in listed] == [150_114_757, 158_293_431]


def test_hrrr_surface_analysis_fetches_and_restores(restored: FetchedAsset) -> None:
    assert not restored.from_cache
    assert restored.path.stat().st_size == 150_114_757


def test_hrrr_surface_cape_opens_with_grib_reader(restored: FetchedAsset) -> None:
    if find_spec("eccodes") is None or find_spec("xarray") is None:
        pytest.skip("grib extra not installed")
    # The GRIB2 reader adds ``select``; the call stays dynamic so pyright passes before it lands.
    options: dict[str, Any] = {"select": {"shortName": "cape", "typeOfLevel": "surface"}}
    fields = restored.open(**options)
    (name,) = list(fields.data_vars)
    assert fields[name].shape == (1059, 1799)
    assert fields[name].attrs["units"].replace("**", "").replace(" ", "") in {"Jkg-1", "J/kg"}
