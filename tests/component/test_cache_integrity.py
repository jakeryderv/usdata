from pathlib import Path

import pytest
import respx

from usdata import fetch_asset, provenance
from usdata.cache import asset_path
from usdata.models import Asset, Protocol
from usdata.providers.noaa.ghcnd import DATA_URL
from usdata.registry import default_registry


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


def test_a_cache_directory_symlinked_elsewhere_is_still_the_cache(tmp_path: Path) -> None:
    """A user may move part of the cache to a bigger disk; only ids are held to the root."""
    root, elsewhere = tmp_path / "cache", tmp_path / "bigger-disk"
    elsewhere.mkdir()
    root.mkdir()
    (root / "noaa").symlink_to(elsewhere, target_is_directory=True)
    asset = Asset(id="data", dataset_id="noaa:ghcn-daily", href=DATA_URL, protocol=Protocol.HTTP)
    path = asset_path(asset, root)
    assert path == root.resolve() / "noaa" / "ghcn-daily" / "data"


@pytest.mark.parametrize("link", ["asset", "sidecar"])
def test_a_symlinked_cache_file_is_replaced_not_written_through(tmp_path: Path, link: str) -> None:
    root, outside = tmp_path / "cache", tmp_path / "outside"
    outside.mkdir()
    asset = Asset(id="data", dataset_id="noaa:ghcn-daily", href=DATA_URL, protocol=Protocol.HTTP)
    path = asset_path(asset, root)
    path.parent.mkdir(parents=True)
    target = path if link == "asset" else provenance.sidecar_path(path)
    target.symlink_to(outside / "victim")
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(200, content=b"data")
        fetch_asset(default_registry().get("noaa:ghcn-daily"), asset, root=root)
    assert list(outside.iterdir()) == []
    assert not target.is_symlink() and target.is_file()


@pytest.mark.parametrize("asset_id", ["data.provenance.json", ".data.x1y2.part"])
def test_an_id_naming_a_file_the_cache_keeps_for_itself_is_rejected(
    tmp_path: Path, asset_id: str
) -> None:
    asset = Asset(id=asset_id, dataset_id="noaa:ghcn-daily", href=DATA_URL, protocol=Protocol.HTTP)
    with pytest.raises(ValueError, match="keeps for itself"):
        asset_path(asset, tmp_path)
