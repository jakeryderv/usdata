"""One HRRR surface analysis: whole-file fetch and restore, and a two-message partial fetch."""

from importlib.util import find_spec
from typing import Any

import pytest

from usdata import FetchedAsset, build_query, get
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
# CAPE at the surface and 0-3 km helicity, as the run's .idx sidecar names them.
MESSAGES = "CAPE:surface,HLCY:3000-0 m above ground"
PARTIAL_MANIFEST = f"""name: hrrr-messages
sources:
  - dataset: noaa:hrrr
    start: 2024-05-06T20:00:00Z
    end: 2024-05-06T20:00:00Z
    params: {{cycle: 20, forecast_hour: 0, messages: "{MESSAGES}"}}
"""
WHOLE_BYTES = 150_114_757
PART_BYTES = 1_838_460


@pytest.fixture(scope="module")
def restored(tmp_path_factory: pytest.TempPathFactory) -> FetchedAsset:
    """The 150 MB analysis, fetched once per module, then restored through its lockfile."""
    root = tmp_path_factory.mktemp("hrrr")
    manifest = root / "dataset.yaml"
    manifest.write_text(MANIFEST)
    result = pull(manifest, root=root / "cache")
    (item,) = result.fetched
    assert item.asset.id == "hrrr.20240506.t20z.wrfsfcf00.grib2"
    assert item.path.stat().st_size == WHOLE_BYTES
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
    assert [asset.size for asset in listed] == [WHOLE_BYTES, 158_293_431]


def test_hrrr_surface_analysis_fetches_and_restores(restored: FetchedAsset) -> None:
    assert not restored.from_cache
    assert restored.path.stat().st_size == WHOLE_BYTES


def test_hrrr_surface_cape_opens_with_grib_reader(restored: FetchedAsset) -> None:
    if find_spec("eccodes") is None or find_spec("xarray") is None:
        pytest.skip("grib extra not installed")
    # The GRIB2 reader adds ``select``; the call stays dynamic so pyright passes before it lands.
    options: dict[str, Any] = {"select": {"shortName": "cape", "typeOfLevel": "surface"}}
    fields = restored.open(**options)
    (name,) = list(fields.data_vars)
    assert fields[name].shape == (1059, 1799)
    assert fields[name].attrs["units"].replace("**", "").replace(" ", "") in {"Jkg-1", "J/kg"}


@pytest.fixture(scope="module")
def part(tmp_path_factory: pytest.TempPathFactory) -> FetchedAsset:
    """Two messages of the same analysis, fetched by byte range and restored from the pin."""
    root = tmp_path_factory.mktemp("hrrr-messages")
    manifest = root / "dataset.yaml"
    manifest.write_text(PARTIAL_MANIFEST)
    result = pull(manifest, root=root / "cache")
    (item,) = result.fetched
    assert item.asset.href.endswith("#messages=105,131")
    assert item.asset.size == PART_BYTES
    assert item.path.stat().st_size == PART_BYTES
    assert item.path.read_bytes()[:4] == b"GRIB"
    assert item.provenance.object_size == WHOLE_BYTES
    assert [(part.start, part.end) for part in item.provenance.ranges] == [
        (64292396, 65005961),
        (96828629, 97953522),
    ]
    item.path.unlink()
    again = pull(manifest, root=root / "cache")
    assert again.from_lockfile and again.lockfile == result.lockfile
    assert again.fetched[0].provenance.checksum == item.provenance.checksum
    assert verify(manifest, root=root / "cache") == []
    return again.fetched[0]


def test_hrrr_two_messages_are_a_hundredth_of_the_whole_file(part: FetchedAsset) -> None:
    assert part.path.stat().st_size == PART_BYTES
    assert PART_BYTES * 50 < WHOLE_BYTES
    assert part.provenance.transformations == [
        "grib2 messages 105,131 concatenated from "
        "s3://noaa-hrrr-bdp-pds/hrrr.20240506/conus/hrrr.t20z.wrfsfcf00.grib2"
    ]


def test_hrrr_partial_file_opens_as_two_fields(part: FetchedAsset) -> None:
    if find_spec("eccodes") is None or find_spec("xarray") is None:
        pytest.skip("grib extra not installed")
    fields = part.open()
    assert {name.split("_")[0] for name in fields.data_vars} == {"cape", "hlcy"}
    for name in fields.data_vars:
        assert fields[name].shape == (1059, 1799)
    options: dict[str, Any] = {"select": {"shortName": "cape"}}
    only_cape = part.open(**options)
    assert list(only_cape.data_vars) == ["cape"]
