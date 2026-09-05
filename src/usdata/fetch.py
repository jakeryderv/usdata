"""Core fetch loop: resolve a query, download assets through the cache, record provenance."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from usdata import provenance
from usdata.cache import asset_path, sha256_file
from usdata.models import Asset, Dataset, Provenance, Query
from usdata.providers import load_adapter


class ChecksumMismatch(RuntimeError):
    pass


class FetchedAsset(BaseModel):
    asset: Asset
    path: Path
    provenance: Provenance
    from_cache: bool


def fetch_asset(
    dataset: Dataset, asset: Asset, *, root: Path | None = None, force: bool = False
) -> FetchedAsset:
    """Fetch one asset via its provider unless it is already cached with a provenance sidecar."""
    path = asset_path(asset, root)
    if not force and path.exists() and provenance.sidecar_path(path).exists():
        return FetchedAsset(
            asset=asset, path=path, provenance=provenance.read(path), from_cache=True
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    load_adapter(dataset).fetch(asset, path)
    if asset.checksum and (got := sha256_file(path)) != asset.checksum:
        path.unlink(missing_ok=True)
        raise ChecksumMismatch(f"{asset.id}: expected {asset.checksum}, got {got}")
    prov = provenance.record(dataset, asset, path)
    provenance.write(prov, path)
    return FetchedAsset(asset=asset, path=path, provenance=prov, from_cache=False)


def fetch(
    dataset: Dataset, query: Query, *, root: Path | None = None, force: bool = False
) -> list[FetchedAsset]:
    """Resolve ``query`` against ``dataset`` and fetch everything it matches."""
    assets = load_adapter(dataset).list_assets(query)
    return [fetch_asset(dataset, a, root=root, force=force) for a in assets]
