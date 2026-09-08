"""Core fetch loop: resolve a query, download assets through the cache, record provenance."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from usdata import provenance
from usdata._files import staged_path
from usdata.cache import asset_path, sha256_file
from usdata.models import Asset, Dataset, Provenance, Query
from usdata.providers import Provider, load_adapter


class ChecksumMismatch(RuntimeError):
    """A fetched file's sha256 did not match the checksum the adapter declared."""


class FetchedAsset(BaseModel):
    """One asset on disk with its provenance and whether the cache satisfied it."""

    asset: Asset
    path: Path
    provenance: Provenance
    from_cache: bool

    def open(
        self,
        *,
        reader: str | None = None,
        dtype: dict[str, str] | None = None,
        parse_dates: list[str] | None = None,
        usecols: list[str] | None = None,
        nrows: int | None = None,
    ) -> Any:
        """Open this local CSV as a DataFrame; requires the ``pandas`` extra.

        ERDDAP units are kept in ``frame.attrs["units"]`` and source provenance
        in ``frame.attrs["usdata"]``. See ``usdata.readers.open_asset`` for options.
        Cached files and provenance sidecars are never changed.
        """
        from usdata.readers import open_asset

        return open_asset(
            self, reader=reader, dtype=dtype, parse_dates=parse_dates, usecols=usecols, nrows=nrows
        )


def _fetch_asset(
    dataset: Dataset,
    asset: Asset,
    adapter: Provider,
    *,
    root: Path | None = None,
    force: bool = False,
) -> FetchedAsset:
    if asset.dataset_id != dataset.id:
        raise ValueError(f"asset dataset {asset.dataset_id!r} does not match {dataset.id!r}")
    path = asset_path(asset, root)
    if not force and path.is_file():
        try:
            prov = provenance.read(path)
        except (ValueError, OSError):
            prov = None
        if (
            prov is not None
            and prov.dataset_id == dataset.id
            and prov.provider == dataset.provider
            and prov.source_url == asset.href
            and prov.size == path.stat().st_size
            and (asset.checksum is None or prov.checksum == asset.checksum)
            and sha256_file(path) == prov.checksum
        ):
            return FetchedAsset(asset=asset, path=path, provenance=prov, from_cache=True)
    with staged_path(path) as tmp:
        adapter.fetch(asset, tmp)
        prov = provenance.record(dataset, asset, tmp)
        if asset.checksum and prov.checksum != asset.checksum:
            raise ChecksumMismatch(f"{asset.id}: expected {asset.checksum}, got {prov.checksum}")
    # A crash between replacements leaves a detectable mismatch, never a trusted partial file.
    provenance.write(prov, path)
    return FetchedAsset(asset=asset, path=path, provenance=prov, from_cache=False)


def fetch_asset(
    dataset: Dataset, asset: Asset, *, root: Path | None = None, force: bool = False
) -> FetchedAsset:
    """Fetch one asset, reusing the cache only when bytes and provenance agree."""
    with load_adapter(dataset) as adapter:
        return _fetch_asset(dataset, asset, adapter, root=root, force=force)


def fetch(
    dataset: Dataset, query: Query, *, root: Path | None = None, force: bool = False
) -> list[FetchedAsset]:
    """Resolve and fetch a query, sharing one adapter and closing its owned resources."""
    with load_adapter(dataset) as adapter:
        assets = adapter.list_assets(query)
        return [_fetch_asset(dataset, a, adapter, root=root, force=force) for a in assets]
