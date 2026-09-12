"""Resolve a manifest to assets, fetch them, and pin the result in a lockfile.

``pull`` has two modes. Without a lockfile (or with ``force``) it resolves every
source through its adapter, fetches, and writes the lockfile. With a lockfile it
fetches exactly the assets pinned there, verifying checksums, and never
re-resolves queries, so the inputs are reproducible even if upstream listings
change. When upstream bytes no longer match a pin, restore reports every such
asset at once; ``update`` accepts new bytes for selected assets or datasets and
rewrites only those pins. ``verify`` re-hashes cached files against the lockfile
without fetching anything.
"""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from usdata import __version__, _progress, provenance
from usdata.cache import asset_path, sha256_file
from usdata.fetch import ChecksumMismatch, FetchedAsset, _fetch_asset, fetch
from usdata.manifest import LockedAsset, Lockfile, Manifest, lockfile_path
from usdata.providers import Provider, load_adapter
from usdata.registry import Registry, default_registry


class ManifestChanged(RuntimeError):
    """The manifest was edited after its lockfile was written; re-resolve with force."""


class UnknownDatasets(ValueError):
    """The manifest references dataset ids the registry does not know."""


class EmptySource(RuntimeError):
    """A required manifest source resolved to no assets."""


class UnknownAssets(ValueError):
    """Update selectors name no asset or dataset in the lockfile."""


def _check_manifest(manifest_path: Path, lock: Lockfile) -> None:
    if sha256_file(manifest_path) != lock.manifest_checksum:
        raise ManifestChanged(
            f"{manifest_path.name} changed since {lockfile_path(manifest_path).name} was written; "
            "pull with force to re-resolve"
        )


class Drift(BaseModel):
    """One lockfile entry whose local copy is missing or altered, or whose source moved on."""

    asset_id: str
    dataset_id: str
    path: Path
    problem: str  # "missing", "checksum mismatch", or "upstream changed"


class UpstreamChanged(ChecksumMismatch):
    """Pinned URLs returned different bytes than the lockfile recorded; nothing was rewritten."""

    def __init__(self, drift: list[Drift]) -> None:
        self.drift = drift
        ids = ", ".join(d.asset_id for d in drift)
        super().__init__(
            f"{len(drift)} asset(s) changed upstream: {ids}; "
            "pull with update to accept new bytes for named assets or datasets"
        )


class PullResult(BaseModel):
    """What a pull did."""

    lockfile: Lockfile
    lockfile_path: Path
    fetched: list[FetchedAsset]
    from_lockfile: bool
    updated: list[str] = Field(
        default_factory=list, description="Ids of assets whose pins were rewritten by update"
    )


def _load(manifest_path: Path, registry: Registry) -> Manifest:
    manifest = Manifest.load(manifest_path)
    missing = manifest.validate_against(registry)
    if missing:
        raise UnknownDatasets(f"unknown datasets in manifest: {', '.join(missing)}")
    return manifest


def resolve(
    manifest_path: Path, *, root: Path | None = None, registry: Registry | None = None
) -> PullResult:
    """Resolve every source through its adapter, fetch, and write a fresh lockfile."""
    reg = registry or default_registry()
    manifest = _load(manifest_path, reg)
    fetched: list[FetchedAsset] = []
    locked: list[LockedAsset] = []
    for index, source in enumerate(manifest.sources, start=1):
        dataset = reg.get(source.dataset)
        items = fetch(dataset, source.to_query(), root=root)
        if not items and not source.allow_empty:
            raise EmptySource(
                f"source {index} ({dataset.id}) matched no assets; "
                "check the query or set allow_empty: true for this source"
            )
        for item in items:
            fetched.append(item)
            pinned = item.asset.model_copy(update={"checksum": item.provenance.checksum})
            locked.append(LockedAsset(asset=pinned, provenance=item.provenance))
    lock = Lockfile(
        manifest=manifest.name,
        manifest_checksum=sha256_file(manifest_path),
        generated_at=datetime.now(UTC),
        usdata_version=__version__,
        assets=locked,
    )
    out = lockfile_path(manifest_path)
    lock.save(out)
    return PullResult(lockfile=lock, lockfile_path=out, fetched=fetched, from_lockfile=False)


def _selected(lock: Lockfile, update: Iterable[str]) -> set[str]:
    """Ids of the locked assets that ``update`` selectors (asset or dataset ids) name."""
    selectors = set(update)
    known = {e.asset.id for e in lock.assets} | {e.asset.dataset_id for e in lock.assets}
    if unknown := sorted(selectors - known):
        raise UnknownAssets(f"update selects nothing in the lockfile: {', '.join(unknown)}")
    return {
        e.asset.id
        for e in lock.assets
        if e.asset.id in selectors or e.asset.dataset_id in selectors
    }


def restore(
    manifest_path: Path,
    *,
    root: Path | None = None,
    registry: Registry | None = None,
    update: Iterable[str] = (),
) -> PullResult:
    """Fetch exactly what the lockfile pins. Re-downloads missing or altered files.

    ``update`` names assets or datasets whose current upstream bytes replace their
    pins. Every other entry must still match; if any does not, the whole run raises
    ``UpstreamChanged`` listing them and the lockfile is left as it was.
    """
    reg = registry or default_registry()
    lock_path = lockfile_path(manifest_path)
    lock = Lockfile.load(lock_path)
    _check_manifest(manifest_path, lock)
    selected = _selected(lock, update)
    fetched: list[FetchedAsset] = []
    entries: list[LockedAsset] = []
    updated: list[str] = []
    drift: list[Drift] = []
    _progress.batch([entry.provenance.size for entry in lock.assets])
    adapters: dict[str, Provider] = {}
    with ExitStack() as stack:
        for entry in lock.assets:
            dataset = reg.get(entry.asset.dataset_id)
            path = asset_path(entry.asset, root)
            refresh = entry.asset.id in selected
            if path.is_file() and not refresh:
                _progress.emit(
                    _progress.AssetProgress(entry.asset.id, "start", entry.provenance.size)
                )
            if path.is_file() and not refresh and sha256_file(path) == entry.provenance.checksum:
                provenance.write(entry.provenance, path)
                _progress.emit(
                    _progress.AssetProgress(entry.asset.id, "cached", entry.provenance.size)
                )
                fetched.append(
                    FetchedAsset(
                        asset=entry.asset, path=path, provenance=entry.provenance, from_cache=True
                    )
                )
                entries.append(entry)
                continue
            if dataset.id not in adapters:
                adapters[dataset.id] = stack.enter_context(load_adapter(dataset))
            adapter = adapters[dataset.id]
            if refresh:
                # Fetch unpinned so whatever upstream serves now becomes the new pin.
                unpinned = entry.asset.model_copy(update={"checksum": None})
                item = _fetch_asset(dataset, unpinned, adapter, root=root, force=True)
                if item.provenance.checksum == entry.provenance.checksum:
                    entries.append(entry)  # Same bytes: keep the original pin and record.
                else:
                    pinned = item.asset.model_copy(update={"checksum": item.provenance.checksum})
                    entries.append(LockedAsset(asset=pinned, provenance=item.provenance))
                    updated.append(entry.asset.id)
                fetched.append(item)
                continue
            pinned = entry.asset.model_copy(update={"checksum": entry.provenance.checksum})
            try:
                fetched.append(_fetch_asset(dataset, pinned, adapter, root=root, force=True))
            except ChecksumMismatch:
                drift.append(
                    Drift(
                        asset_id=entry.asset.id,
                        dataset_id=entry.asset.dataset_id,
                        path=path,
                        problem="upstream changed",
                    )
                )
                continue
            entries.append(entry)
    if drift:
        raise UpstreamChanged(drift)
    if updated:
        lock = lock.model_copy(update={"assets": entries})
        lock.save(lock_path)
    return PullResult(
        lockfile=lock,
        lockfile_path=lock_path,
        fetched=fetched,
        from_lockfile=True,
        updated=updated,
    )


def pull(
    manifest_path: Path,
    *,
    root: Path | None = None,
    force: bool = False,
    registry: Registry | None = None,
    update: Iterable[str] = (),
) -> PullResult:
    """Restore from the lockfile if one exists, otherwise resolve and create it.

    ``update`` names assets or datasets whose pins should follow current upstream
    bytes; it needs an existing lockfile and is exclusive with ``force``.
    """
    update = list(update)
    if update and force:
        raise ValueError("update and force are exclusive; force re-resolves every source")
    if force or not lockfile_path(manifest_path).exists():
        if update:
            raise ValueError(f"no lockfile at {lockfile_path(manifest_path)}; pull first")
        return resolve(manifest_path, root=root, registry=registry)
    return restore(manifest_path, root=root, registry=registry, update=update)


def verify(manifest_path: Path, *, root: Path | None = None) -> list[Drift]:
    """Check manifest consistency, then compare cached files against the lockfile."""
    lock = Lockfile.load(lockfile_path(manifest_path))
    _check_manifest(manifest_path, lock)
    drift: list[Drift] = []
    for entry in lock.assets:
        path = asset_path(entry.asset, root)
        if not path.exists():
            problem = "missing"
        elif sha256_file(path) != entry.provenance.checksum:
            problem = "checksum mismatch"
        else:
            continue
        drift.append(
            Drift(
                asset_id=entry.asset.id,
                dataset_id=entry.asset.dataset_id,
                path=path,
                problem=problem,
            )
        )
    return drift


__all__ = [
    "ChecksumMismatch",
    "Drift",
    "EmptySource",
    "ManifestChanged",
    "PullResult",
    "UnknownAssets",
    "UnknownDatasets",
    "UpstreamChanged",
    "provenance",
    "pull",
    "resolve",
    "restore",
    "verify",
]
