"""One small GOES-18 ABI CONUS NetCDF scene, with checksum-locked restoration."""

from importlib.util import find_spec
from pathlib import Path

import pytest

from usdata.pull import pull, verify

pytestmark = pytest.mark.live


def test_goes18_small_scene_restore(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: small-goes-scene
sources:
  - dataset: noaa:goes-abi
    start: 2024-05-06T12:01:18.1Z
    end: 2024-05-06T12:01:18.1Z
    params: {satellite: 18, channel: 6, product: ABI-L2-CMIPC}
""")
    result = pull(manifest, root=tmp_path / "cache")
    (item,) = result.fetched
    assert item.asset.id.startswith("OR_ABI-L2-CMIPC-M6C06_G18_")
    assert item.asset.time is not None and item.asset.time.start is not None
    assert item.asset.time.start.isoformat() == "2024-05-06T12:01:18.100000+00:00"
    assert item.path.stat().st_size == item.asset.size
    with item.path.open("rb") as stream:
        assert stream.read(8) == b"\x89HDF\r\n\x1a\n"
    item.path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and not restored.fetched[0].from_cache
    assert restored.lockfile == result.lockfile
    assert verify(manifest, root=tmp_path / "cache") == []

    if all(find_spec(name) is not None for name in ("xarray", "h5netcdf", "h5py")):
        scene = restored.fetched[0].open()
        assert scene.CMI.attrs["units"] == "1"  # channel 6 reflectance
        assert scene.CMI.dims == ("y", "x")
        assert scene.attrs["usdata"]["provenance"]["checksum"] == item.provenance.checksum
        assert verify(manifest, root=tmp_path / "cache") == []
