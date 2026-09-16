"""Core fetch loop: resolve a query, download assets through the cache, record provenance."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from usdata import _progress, provenance
from usdata._files import staged_path
from usdata.cache import asset_path, sha256_file
from usdata.models import Asset, Dataset, Provenance, Query
from usdata.providers import Provider, load_adapter

if TYPE_CHECKING:
    from usdata.inspect import Summary


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
        sweep: int | list[int] | None = None,
        select: Mapping[str, Any] | None = None,
        strict: bool = False,
    ) -> Any:
        """Open local data with an optional ``pandas``, ``radar``, ``netcdf``, or ``grib`` reader.

        ERDDAP units are kept in ``frame.attrs["units"]`` and source provenance
        in ``frame.attrs["usdata"]``. NEXRAD returns a xarray DataTree with provenance
        in ``radar.attrs["usdata"]``. NetCDF4 and GRIB2 return a loaded xarray Dataset
        with matching provenance in its attributes, and with units and long names
        the file leaves unstated filled from the registry entry's variables. See
        ``usdata.readers.open_asset`` for options. Use ``sweep=0`` or ``sweep=[0, 2]``
        to load selected zero-based radar sweeps, and
        ``select={"shortName": "cape", "typeOfLevel": "surface"}``
        to choose GRIB2 messages; ``strict=True`` raises instead of warning when a
        GRIB2 select value matches none of the selected messages. Cached files and
        provenance sidecars are never changed.
        """
        from usdata.readers import open_asset

        return open_asset(
            self,
            reader=reader,
            dtype=dtype,
            parse_dates=parse_dates,
            usecols=usecols,
            nrows=nrows,
            sweep=sweep,
            select=select,
            strict=strict,
        )

    def inspect(self) -> Summary:
        """Summarize this file: provenance, format, and what that format holds.

        CSV columns and a capped row count need no extra; NetCDF4 variables and
        GRIB2 messages need the same extras ``open`` does, and a missing one
        yields a summary with no detail and a note naming it. Like ``open``,
        this reads the cached file and changes nothing. See
        ``usdata.inspect.inspect_asset``.
        """
        from usdata.inspect import inspect_asset

        return inspect_asset(self)


def _sidecar_not_older(path: Path) -> bool:
    """Whether ``path`` still carries the mtime it had when its sidecar was written.

    The sidecar is always written after the data file lands, so a data file that
    is newer than its sidecar was touched afterwards and the record no longer
    implies its bytes. See ADR 0024.
    """
    try:
        sidecar = provenance.sidecar_path(path).stat()
        return path.stat().st_mtime_ns <= sidecar.st_mtime_ns
    except OSError:
        return False


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
    _progress.emit(_progress.AssetProgress(asset.id, "start", asset.size))
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
            # Trust an untouched cached file; hash whenever anything is unclear.
            and (_sidecar_not_older(path) or sha256_file(path) == prov.checksum)
        ):
            _progress.emit(_progress.AssetProgress(asset.id, "cached", prov.size))
            return FetchedAsset(asset=asset, path=path, provenance=prov, from_cache=True)
    with staged_path(path) as tmp:
        adapter.fetch(asset, tmp)
        prov = provenance.record(dataset, asset, tmp)
        if asset.checksum and prov.checksum != asset.checksum:
            raise ChecksumMismatch(f"{asset.id}: expected {asset.checksum}, got {prov.checksum}")
    # A crash between replacements leaves a detectable mismatch, never a trusted partial file.
    provenance.write(prov, path)
    _progress.emit(_progress.AssetProgress(asset.id, "fetched", prov.size))
    return FetchedAsset(asset=asset, path=path, provenance=prov, from_cache=False)


def fetch_asset(
    dataset: Dataset, asset: Asset, *, root: Path | None = None, force: bool = False
) -> FetchedAsset:
    """Fetch one asset, reusing the cache only when its provenance still describes it."""
    with load_adapter(dataset) as adapter:
        return _fetch_asset(dataset, asset, adapter, root=root, force=force)


def _fetch_with(
    adapter: Provider,
    dataset: Dataset,
    query: Query,
    *,
    root: Path | None = None,
    force: bool = False,
) -> list[FetchedAsset]:
    """Run the loop on an adapter the caller opened, so one adapter can serve many queries."""
    assets = adapter.list_assets(query)
    _progress.batch([asset.size for asset in assets])
    return [_fetch_asset(dataset, a, adapter, root=root, force=force) for a in assets]


def fetch(
    dataset: Dataset, query: Query, *, root: Path | None = None, force: bool = False
) -> list[FetchedAsset]:
    """Resolve and fetch a query, sharing one adapter and closing its owned resources."""
    with load_adapter(dataset) as adapter:
        return _fetch_with(adapter, dataset, query, root=root, force=force)
