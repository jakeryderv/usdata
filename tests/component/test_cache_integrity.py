from pathlib import Path

import pytest

from usdata import provenance
from usdata.cache import asset_path
from usdata.models import Asset, Protocol
from usdata.providers.noaa.ghcnd import DATA_URL


@pytest.mark.parametrize(
    "dataset_id,asset_id",
    [
        ("noaa:../../outside", "data"),
        ("/tmp:dataset", "data"),
        ("noaa:dataset", ".."),
        ("noaa:dataset", r"..\outside"),
    ],
)
def test_unsafe_cache_components_rejected(tmp_path: Path, dataset_id: str, asset_id: str) -> None:
    asset = Asset(id=asset_id, dataset_id=dataset_id, href=DATA_URL, protocol=Protocol.HTTP)
    with pytest.raises(ValueError, match="unsafe"):
        asset_path(asset, tmp_path)


@pytest.mark.parametrize("link", ["provider", "asset", "sidecar"])
def test_cache_symlink_escape_rejected(tmp_path: Path, link: str) -> None:
    root, outside = tmp_path / "cache", tmp_path / "outside"
    outside.mkdir()
    asset = Asset(id="data", dataset_id="noaa:ghcn-daily", href=DATA_URL, protocol=Protocol.HTTP)
    path = asset_path(asset, root)
    path.parent.mkdir(parents=True)
    if link == "provider":
        path.parent.rmdir()
        path.parent.parent.rmdir()
        (root / "noaa").symlink_to(outside, target_is_directory=True)
    else:
        target = path if link == "asset" else provenance.sidecar_path(path)
        target.symlink_to(outside / "victim")
    with pytest.raises(ValueError, match="escapes root"):
        asset_path(asset, root)
    assert list(outside.iterdir()) == []
