"""One 20-second GOES-16 GLM detection file, with checksum-locked restoration."""

from pathlib import Path

import pytest

from usdata.pull import pull, verify

pytestmark = pytest.mark.live


def restored_file(tmp_path: Path):
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: one-glm-file
sources:
  - dataset: noaa:goes-glm
    start: 2024-05-06T20:00:00Z
    end: 2024-05-06T20:00:00Z
    params: {satellite: 16}
""")
    result = pull(manifest, root=tmp_path / "cache")
    (item,) = result.fetched
    assert item.asset.id.startswith("OR_GLM-L2-LCFA_G16_s20241272000000_e20241272000200_")
    assert item.asset.time is not None and item.asset.time.start is not None
    assert item.asset.time.start.isoformat() == "2024-05-06T20:00:00+00:00"
    assert item.path.stat().st_size == item.asset.size
    with item.path.open("rb") as stream:
        assert stream.read(8) == b"\x89HDF\r\n\x1a\n"
    item.path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and not restored.fetched[0].from_cache
    assert restored.lockfile == result.lockfile
    assert verify(manifest, root=tmp_path / "cache") == []
    return restored.fetched[0]


def test_goes16_glm_file_restore(tmp_path: Path) -> None:
    restored_file(tmp_path)


@pytest.mark.netcdf
def test_goes16_glm_file_decodes_with_netcdf_reader(tmp_path: Path) -> None:
    for dependency in ("xarray", "h5netcdf", "h5py"):
        pytest.importorskip(dependency)
    item = restored_file(tmp_path)
    detections = item.open()
    assert detections.attrs["usdata"]["provenance"]["checksum"] == item.provenance.checksum
    flashes = detections["flash_energy"]
    assert flashes.dims == ("number_of_flashes",)
    assert flashes.attrs["units"] == "J"
    assert flashes.sizes["number_of_flashes"] > 0
    assert detections["flash_lat"].sizes == flashes.sizes
    assert detections["event_energy"].dims == ("number_of_events",)
    assert verify(tmp_path / "dataset.yaml", root=tmp_path / "cache") == []
