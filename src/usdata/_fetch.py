"""Core fetch loop: resolve a query, download assets through the cache, record provenance."""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from usdata import _progress, provenance
from usdata._files import staged_path
from usdata.cache import asset_path, sha256_file
from usdata.models import Asset, Dataset, Provenance, Query
from usdata.providers import Provider, load_adapter

if TYPE_CHECKING:
    # Each is an optional extra: without it installed the result is simply untyped.
    import pandas as pd  # pyright: ignore[reportMissingImports]
    import xarray as xr  # pyright: ignore[reportMissingImports]

    from usdata.inspect import Summary


class ChecksumMismatch(RuntimeError):
    """A fetched file's sha256 did not match the checksum the adapter declared."""


class FetchedAsset(BaseModel):
    """One asset on disk with its provenance and whether the cache satisfied it."""

    asset: Asset
    path: Path
    provenance: Provenance
    from_cache: bool

    def open(self) -> Any:
        """Open local data with the reader its format implies, with that reader's defaults.

        CSV and ERDDAP CSV, HURDAT2 and AQS daily JSON return a pandas DataFrame;
        NetCDF4 and GRIB2 a loaded xarray Dataset; NEXRAD Level II an xarray
        DataTree. Provenance is kept in the result's ``attrs["usdata"]``. A file
        that needs options, or whose metadata leaves its format ambiguous, is
        opened with the method for its format instead: ``open_csv``,
        ``open_nexrad``, ``open_grib2``, or ``open_netcdf``. Cached files and
        provenance sidecars are never changed. See ``usdata.readers.open_asset``.
        """
        from usdata.readers import open_asset

        return open_asset(self)

    def open_csv(
        self,
        *,
        dtype: dict[str, str] | None = None,
        parse_dates: list[str] | None = None,
        usecols: list[str] | None = None,
        nrows: int | None = None,
        units_row: bool | None = None,
    ) -> pd.DataFrame:
        """Open a CSV as a pandas DataFrame; see ``usdata.readers.open_csv``.

        ``units_row`` says whether a units row follows the header, as in ERDDAP
        CSV, and is inferred when ``None``; the units go to ``frame.attrs["units"]``.
        """
        from usdata.readers import open_csv

        return open_csv(
            self,
            dtype=dtype,
            parse_dates=parse_dates,
            usecols=usecols,
            nrows=nrows,
            units_row=units_row,
        )

    def open_nexrad(self, *, sweep: int | list[int] | None = None) -> xr.DataTree:
        """Open a NEXRAD Level II volume as an xarray DataTree; see ``usdata.readers.open_nexrad``.

        Use ``sweep=0`` or ``sweep=[0, 2]`` to load selected zero-based sweeps.
        """
        from usdata.readers import open_nexrad

        return open_nexrad(self, sweep=sweep)

    def open_grib2(
        self, *, select: Mapping[str, Any] | None = None, strict: bool = False
    ) -> xr.Dataset:
        """Open GRIB2 messages as one xarray Dataset; see ``usdata.readers.open_grib2``.

        ``select={"shortName": "cape", "typeOfLevel": "surface"}`` chooses
        messages; ``strict=True`` raises instead of warning when a select value
        matches none of the selected messages.
        """
        from usdata.readers import open_grib2

        return open_grib2(self, select=select, strict=strict)

    def open_netcdf(self) -> xr.Dataset:
        """Open a NetCDF4 file as an xarray Dataset; see ``usdata.readers.open_netcdf``."""
        from usdata.readers import open_netcdf

        return open_netcdf(self)

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


def _cached(dataset: Dataset, asset: Asset, path: Path) -> Provenance | None:
    """The record of a file at ``path`` that still describes ``asset``, or None if there is none."""
    if not path.is_file():
        return None
    try:
        prov = provenance.read(path)
    except (ValueError, OSError):
        return None
    if (
        prov.dataset_id == dataset.id
        and prov.provider == dataset.provider
        and prov.source_url == asset.href
        and prov.size == path.stat().st_size
        # A listing that now reports another size describes a rebuilt file.
        and (asset.size is None or prov.size == asset.size)
        and (asset.checksum is None or prov.checksum == asset.checksum)
        # Trust an untouched cached file; hash whenever anything is unclear.
        and (_sidecar_not_older(path) or sha256_file(path) == prov.checksum)
    ):
        return prov
    return None


def _fetch_asset(
    dataset: Dataset,
    asset: Asset,
    adapter: Provider,
    *,
    root: Path | None = None,
    force: bool = False,
    pinned: Provenance | None = None,
    staging: Path | None = None,
) -> FetchedAsset:
    """Fetch one asset through the cache, passing any pinned record to the adapter.

    ``pinned`` is the provenance a lockfile holds for this asset. The adapter sees
    it through ``prepare_fetch``, so an asset that pins byte ranges is reproduced
    from the record rather than by resolving its query again.

    ``staging`` is a root a download is written under instead of the cache. The
    cache at ``root`` is still checked, and a hit is returned from there; so is
    ``staging``, where an earlier source in the same run may have fetched the
    same asset. A miss comes back with its ``path`` under ``staging``, for the
    caller to move home once it can pin it (ADR 0031).
    """
    if asset.dataset_id != dataset.id:
        raise ValueError(f"asset dataset {asset.dataset_id!r} does not match {dataset.id!r}")
    _progress.emit(_progress.AssetProgress(asset.id, "start", asset.size))
    path = asset_path(asset, root)
    staged = None if staging is None else asset_path(asset, staging)
    # A staged run looks in its staging too, so an asset two sources share is fetched once.
    for candidate in () if force else (path, staged):
        if candidate is not None and (prov := _cached(dataset, asset, candidate)) is not None:
            _progress.emit(_progress.AssetProgress(asset.id, "cached", prov.size))
            return FetchedAsset(asset=asset, path=candidate, provenance=prov, from_cache=True)
    if staged is not None:
        path = staged
    with staged_path(path) as tmp:
        partial = adapter.prepare_fetch(asset, pinned)
        if partial is None:
            adapter.fetch(asset, tmp)
        else:
            adapter.fetch_partial(asset, tmp, partial)
        prov = provenance.record(dataset, asset, tmp, partial, adapter.transformations)
        if asset.checksum and prov.checksum != asset.checksum:
            raise ChecksumMismatch(f"{asset.id}: expected {asset.checksum}, got {prov.checksum}")
    # A crash between replacements leaves a detectable mismatch, never a trusted partial file.
    provenance.write(prov, path)
    _progress.emit(_progress.AssetProgress(asset.id, "fetched", prov.size))
    return FetchedAsset(asset=asset, path=path, provenance=prov, from_cache=False)


def fetch_asset(
    dataset: Dataset,
    asset: Asset,
    *,
    root: str | os.PathLike[str] | None = None,
    force: bool = False,
) -> FetchedAsset:
    """Fetch one asset, reusing the cache only when its provenance still describes it."""
    with load_adapter(dataset) as adapter:
        return _fetch_asset(
            dataset, asset, adapter, root=None if root is None else Path(root), force=force
        )


def _fetch_with(
    adapter: Provider,
    dataset: Dataset,
    query: Query,
    *,
    root: Path | None = None,
    force: bool = False,
    staging: Path | None = None,
) -> list[FetchedAsset]:
    """Run the loop on an adapter the caller opened, so one adapter can serve many queries.

    The listing is put in the order every result promises, by ``asset.time.start``
    then id, so no adapter has to sort and no caller has to sort defensively.
    ``staging`` is passed to each fetch; see ``_fetch_asset``.
    """
    assets = ordered(adapter.list_assets(query))
    return _fetch_listed(adapter, dataset, assets, root=root, force=force, staging=staging)


def _fetch_listed(
    adapter: Provider,
    dataset: Dataset,
    assets: list[Asset],
    *,
    root: Path | None = None,
    force: bool = False,
    staging: Path | None = None,
) -> list[FetchedAsset]:
    """Fetch assets already listed and put in order, as the loop does once it has listed them."""
    _progress.batch([asset.size for asset in assets])
    return [
        _fetch_asset(dataset, a, adapter, root=root, force=force, staging=staging) for a in assets
    ]


def ordered(assets: list[Asset]) -> list[Asset]:
    """``assets`` by start time, then id; assets without a start time come last, by id."""
    return sorted(
        assets,
        key=lambda asset: (
            asset.time is None or asset.time.start is None,
            asset.time.start if asset.time is not None and asset.time.start is not None else _NEVER,
            asset.id,
        ),
    )


_NEVER = datetime.max.replace(tzinfo=UTC)


def fetch(
    dataset: Dataset,
    query: Query,
    *,
    root: str | os.PathLike[str] | None = None,
    force: bool = False,
) -> list[FetchedAsset]:
    """Resolve and fetch a query, sharing one adapter and closing its owned resources."""
    with load_adapter(dataset) as adapter:
        return _fetch_with(
            adapter, dataset, query, root=None if root is None else Path(root), force=force
        )
