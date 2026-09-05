"""Resolve a manifest to assets, fetch them, and pin the result in a lockfile.

``pull`` has two modes. Without a lockfile (or with ``force``) it resolves every
source through its adapter, fetches, and writes the lockfile. With a lockfile it
fetches exactly the assets pinned there, verifying checksums, and never
re-resolves queries, so the inputs are reproducible even if upstream listings
change. ``verify`` re-hashes cached files against the lockfile without
fetching anything.
"""

from __future__ import annotations

from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from usdata import __version__, provenance
from usdata.cache import asset_path, sha256_file
from usdata.fetch import ChecksumMismatch, FetchedAsset, _fetch_asset, fetch
from usdata.manifest import LockedAsset, Lockfile, Manifest, lockfile_path
from usdata.providers import Provider, load_adapter
from usdata.registry import Registry, default_registry


class ManifestChanged(RuntimeError):
    """The manifest was edited after its lockfile was written; re-resolve with force."""


class UnknownDatasets(ValueError):
    """The manifest references dataset ids the registry does not know."""


class Drift(BaseModel):
    """One lockfile entry whose local copy is missing or altered."""

    asset_id: str
    dataset_id: str
    path: Path
    problem: str  # "missing" or "checksum mismatch"


class PullResult(BaseModel):
    """What a pull did."""

    lockfile: Lockfile
    lockfile_path: Path
    fetched: list[FetchedAsset]
    from_lockfile: bool


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
    for source in manifest.sources:
        dataset = reg.get(source.dataset)
        for item in fetch(dataset, source.to_query(), root=root):
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


def restore(
    manifest_path: Path, *, root: Path | None = None, registry: Registry | None = None
) -> PullResult:
    """Fetch exactly what the lockfile pins. Re-downloads missing or altered files."""
    reg = registry or default_registry()
    lock_path = lockfile_path(manifest_path)
    lock = Lockfile.load(lock_path)
    if sha256_file(manifest_path) != lock.manifest_checksum:
        raise ManifestChanged(
            f"{manifest_path.name} changed since {lock_path.name} was written; "
            "pull with force to re-resolve"
        )
    fetched: list[FetchedAsset] = []
    adapters: dict[str, Provider] = {}
    with ExitStack() as stack:
        for entry in lock.assets:
            dataset = reg.get(entry.asset.dataset_id)
            path = asset_path(entry.asset, root)
            if path.is_file() and sha256_file(path) == entry.provenance.checksum:
                provenance.write(entry.provenance, path)
                fetched.append(
                    FetchedAsset(
                        asset=entry.asset, path=path, provenance=entry.provenance, from_cache=True
                    )
                )
                continue
            if dataset.id not in adapters:
                adapters[dataset.id] = stack.enter_context(load_adapter(dataset))
            pinned = entry.asset.model_copy(update={"checksum": entry.provenance.checksum})
            fetched.append(
                _fetch_asset(dataset, pinned, adapters[dataset.id], root=root, force=True)
            )
    return PullResult(lockfile=lock, lockfile_path=lock_path, fetched=fetched, from_lockfile=True)


def pull(
    manifest_path: Path,
    *,
    root: Path | None = None,
    force: bool = False,
    registry: Registry | None = None,
) -> PullResult:
    """Restore from the lockfile if one exists, otherwise resolve and create it."""
    if force or not lockfile_path(manifest_path).exists():
        return resolve(manifest_path, root=root, registry=registry)
    return restore(manifest_path, root=root, registry=registry)


def verify(manifest_path: Path, *, root: Path | None = None) -> list[Drift]:
    """Compare cached files against the lockfile. Empty list means everything matches."""
    lock = Lockfile.load(lockfile_path(manifest_path))
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
    "ManifestChanged",
    "PullResult",
    "UnknownDatasets",
    "provenance",
    "pull",
    "resolve",
    "restore",
    "verify",
]
