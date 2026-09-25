"""Resolve a manifest to assets, fetch them, and pin the result in a lockfile.

``pull`` has two modes. Without a lockfile (or with ``force``) it resolves every
source through its adapter, fetches, and writes the lockfile. With a lockfile it
fetches exactly the assets pinned there, verifying checksums, and never
re-resolves queries, so the inputs are reproducible even if upstream listings
change. When upstream bytes no longer match a pin, restore reports every such
asset at once; ``update`` accepts new bytes for selected assets or datasets and
rewrites only those pins. ``verify`` re-hashes cached files against the lockfile
without fetching anything.

``plan`` prices a manifest without downloading anything: it validates every
source and lists it through the same adapters, so the result says what a pull
would fetch and how many of its bytes the adapters can measure.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from pydantic import BaseModel, Field, computed_field

from usdata import __version__, _progress, mirror, provenance
from usdata._fetch import ChecksumMismatch, FetchedAsset, _fetch_asset, _fetch_with, ordered
from usdata._files import staged_path
from usdata.cache import asset_path, cache_dir, sha256_file
from usdata.manifest import LockedAsset, Lockfile, Manifest, lockfile_path
from usdata.models import Asset, Dataset
from usdata.protocols import http
from usdata.protocols.http import ObjectChanged, RangeNotHonored
from usdata.providers import MissingCredentials, Provider, load_adapter
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
    problem: str = Field(
        description=(
            "'missing', 'checksum mismatch', 'upstream changed', 'gone upstream (<status>)', or "
            "'range refused'; a restore that also tried a mirror appends why the mirror did "
            "not help"
        )
    )


class UpstreamChanged(ChecksumMismatch):
    """Pinned URLs no longer reproduced what the lockfile recorded; nothing was rewritten.

    Each ``Drift`` says how: different bytes, an object that is gone, or a
    refused range request.
    """

    def __init__(self, drift: list[Drift]) -> None:
        self.drift = drift
        ids = ", ".join(d.asset_id for d in drift)
        super().__init__(
            f"{len(drift)} asset(s) changed upstream: {ids}; "
            "pull with update to accept new bytes for named assets or datasets, "
            "or with force to re-resolve"
        )


class PullResult(BaseModel):
    """What a pull did.

    ``fetched`` keeps manifest order, and within a source the assets are ordered
    by start time and then id; ``by_source`` holds the same objects grouped by
    source key, which is a source's ``name`` when it has one and its one-based
    position otherwise, in the same order. ``one`` is for a source that can only
    ever resolve to one asset.
    """

    lockfile: Lockfile
    lockfile_path: Path
    fetched: list[FetchedAsset] = Field(
        description="Every asset, in manifest order, then by start time and id within a source"
    )
    from_lockfile: bool
    updated: list[str] = Field(
        default_factory=list, description="Ids of assets whose pins were rewritten by update"
    )
    mirrored: list[str] = Field(
        default_factory=list,
        description=(
            "Ids of assets the mirror restored instead of the source: because the pinned URL no "
            "longer served their bytes, or, for those also in unchecked, because the source's "
            "credentials are not set; pins are unchanged and each sidecar names the mirror object"
        ),
    )
    unchecked: list[str] = Field(
        default_factory=list,
        description=(
            "Ids of mirrored assets restored without asking their source, because its "
            "credentials are not set, so upstream was not checked for changes (ADR 0039)"
        ),
    )
    by_source: dict[str, list[FetchedAsset]] = Field(
        default_factory=dict,
        description="The same assets grouped by source key, in manifest order",
    )

    def one(self, source: str) -> FetchedAsset:
        """The single asset a source resolved to.

        Args:
            source: The source key: its ``name``, or its one-based position as a string.

        Returns:
            That source's only asset.

        Raises:
            KeyError: No source in the result has that key.
            ValueError: The source resolved to no asset, or to more than one.
        """
        if source not in self.by_source:
            raise KeyError(f"no source {source!r}; sources are {', '.join(self.by_source)}")
        items = self.by_source[source]
        if len(items) != 1:
            raise ValueError(
                f"source {source!r} resolved to {len(items)} assets, not one; use by_source"
            )
        return items[0]


def _by_source(pairs: Iterable[tuple[LockedAsset, FetchedAsset]]) -> dict[str, list[FetchedAsset]]:
    """Group fetched assets by the source key their lockfile entry records.

    Keys come out in manifest order because lockfile entries are written in it,
    and each group is ordered by start time and id, so a lockfile written before
    the core ordered its listings groups the same way as one written after. A
    lockfile written before sources had keys records none; those entries fall
    back to the one-based position of their dataset id among the datasets seen,
    which groups sources that share a dataset together until the manifest names
    them and a forced pull rewrites the lockfile.
    """
    grouped: dict[str, list[FetchedAsset]] = {}
    positions: dict[str, str] = {}
    for entry, item in pairs:
        dataset_id = entry.asset.dataset_id
        if dataset_id not in positions:
            positions[dataset_id] = str(len(positions) + 1)
        grouped.setdefault(entry.source or positions[dataset_id], []).append(item)
    by_id: dict[str, FetchedAsset] = {}
    for items in grouped.values():
        by_id.update({item.asset.id: item for item in items})
        items[:] = [by_id[asset.id] for asset in ordered([item.asset for item in items])]
    return grouped


def _load(manifest_path: Path, registry: Registry) -> Manifest:
    manifest = Manifest.load(manifest_path)
    missing = manifest.validate_against(registry)
    if missing:
        raise UnknownDatasets(f"unknown datasets in manifest: {', '.join(missing)}")
    return manifest


def _checked_adapters(
    manifest: Manifest, registry: Registry, stack: ExitStack
) -> dict[str, Provider]:
    """Open one adapter per distinct dataset and validate every source's parameters through it.

    The whole manifest is checked before the first listing, so a bad source fails
    before any download; each adapter stays open on ``stack`` for the fetches that
    follow, and sources sharing a dataset share its adapter.
    """
    adapters: dict[str, Provider] = {}
    for source in manifest.sources:
        dataset = registry.get(source.dataset)
        if dataset.id not in adapters:
            adapters[dataset.id] = stack.enter_context(load_adapter(dataset))
        adapters[dataset.id].validate_params(source.to_query())
    return adapters


def resolve(
    manifest_path: str | os.PathLike[str],
    *,
    root: str | os.PathLike[str] | None = None,
    registry: Registry | None = None,
) -> PullResult:
    """Resolve every source through its adapter, fetch, and write a fresh lockfile.

    When a lockfile already exists, downloads are staged beside the cache and
    moved into it only after the new lockfile is saved, so a run that fails
    leaves every file the old lockfile pins as it was (ADR 0031). Without one
    there is nothing to protect, and downloads go straight into the cache so a
    failed first pull keeps what it fetched.
    """
    reg = registry or default_registry()
    manifest_path = Path(manifest_path)
    root = None if root is None else Path(root)
    manifest = _load(manifest_path, reg)
    out = lockfile_path(manifest_path)
    fetched: list[FetchedAsset] = []
    locked: list[LockedAsset] = []
    moves: list[tuple[Path, Path]] = []
    with ExitStack() as stack:
        adapters = _checked_adapters(manifest, reg, stack)
        staging = _staging(root, stack) if out.exists() else None
        for key, source in zip(manifest.source_keys(), manifest.sources, strict=True):
            dataset = reg.get(source.dataset)
            items = _fetch_with(
                adapters[dataset.id], dataset, source.to_query(), root=root, staging=staging
            )
            if not items and not source.allow_empty:
                raise EmptySource(
                    f"source {key} ({dataset.id}) matched no assets; "
                    "check the query or set allow_empty: true for this source"
                )
            for item in items:
                home = asset_path(item.asset, root)
                if item.path != home:
                    moves.append((item.path, home))
                    item = item.model_copy(update={"path": home})
                fetched.append(item)
                pinned = item.asset.model_copy(update={"checksum": item.provenance.checksum})
                locked.append(LockedAsset(asset=pinned, provenance=item.provenance, source=key))
        lock = Lockfile(
            manifest=manifest.name,
            manifest_checksum=sha256_file(manifest_path),
            generated_at=datetime.now(UTC),
            usdata_version=__version__,
            assets=locked,
        )
        lock.save(out)
        _commit_staged(moves)
    return PullResult(
        lockfile=lock,
        lockfile_path=out,
        fetched=fetched,
        from_lockfile=False,
        by_source=_by_source(zip(locked, fetched, strict=True)),
    )


class SourcePlan(BaseModel):
    """What one manifest source would fetch, as its adapter listed it."""

    source: str = Field(description="The source's manifest key: its name, or its position")
    dataset_id: str
    assets: list[Asset]

    @computed_field(description="Bytes of the assets whose size the adapter reported")
    @property
    def known_bytes(self) -> int:
        """Total size of the assets this source can measure."""
        return sum(asset.size for asset in self.assets if asset.size is not None)

    @computed_field(description="How many of this source's assets report no size")
    @property
    def unknown_sizes(self) -> int:
        """How many assets their adapter gave no size for."""
        return sum(1 for asset in self.assets if asset.size is None)


class Plan(BaseModel):
    """What pulling a manifest would fetch, priced as far as the adapters can measure.

    An asset whose adapter reports no size contributes nothing to ``known_bytes``
    and counts in ``unknown_sizes`` instead, so the total is a floor rather than
    an estimate. A source that matched nothing is kept with no assets; pull would
    fail on it unless the source sets ``allow_empty``.
    """

    manifest: str
    sources: list[SourcePlan] = Field(description="One entry per manifest source, in order")

    @computed_field(description="How many assets the whole manifest would fetch")
    @property
    def asset_count(self) -> int:
        """How many assets the manifest resolves to."""
        return sum(len(source.assets) for source in self.sources)

    @computed_field(description="Bytes the manifest would fetch that adapters could measure")
    @property
    def known_bytes(self) -> int:
        """Total measured size across every source."""
        return sum(source.known_bytes for source in self.sources)

    @computed_field(description="How many assets across the manifest report no size")
    @property
    def unknown_sizes(self) -> int:
        """How many assets no adapter gave a size for."""
        return sum(source.unknown_sizes for source in self.sources)

    @computed_field(description="Keys of the sources holding at least one unsized asset")
    @property
    def unsized_sources(self) -> list[str]:
        """The sources whose adapters left some size unreported, in manifest order."""
        return [source.source for source in self.sources if source.unknown_sizes]


def plan(manifest_path: str | os.PathLike[str], *, registry: Registry | None = None) -> Plan:
    """List every source through its adapter and price the result; download nothing.

    Validates the whole manifest first, exactly as ``resolve`` does, then makes
    only the requests a listing makes: an S3 listing, or the index and HEAD
    requests a partial-fetch source needs to work out its byte ranges.

    Args:
        manifest_path: Path of the manifest YAML file, as a string or any ``os.PathLike``.
        registry: Registry to resolve dataset ids against; the default one if omitted.

    Returns:
        A ``Plan`` holding each source's assets and the totals over them.
    """
    reg = registry or default_registry()
    manifest = _load(Path(manifest_path), reg)
    sources: list[SourcePlan] = []
    with ExitStack() as stack:
        adapters = _checked_adapters(manifest, reg, stack)
        for key, source in zip(manifest.source_keys(), manifest.sources, strict=True):
            dataset = reg.get(source.dataset)
            assets = ordered(adapters[dataset.id].list_assets(source.to_query()))
            sources.append(SourcePlan(source=key, dataset_id=dataset.id, assets=assets))
    return Plan(manifest=manifest.name, sources=sources)


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
    manifest_path: str | os.PathLike[str],
    *,
    root: str | os.PathLike[str] | None = None,
    registry: Registry | None = None,
    update: Iterable[str] = (),
) -> PullResult:
    """Fetch exactly what the lockfile pins. Re-downloads missing or altered files.

    ``update`` names assets or datasets whose current upstream bytes replace their
    pins. Every other entry must still match; if any does not, the whole run raises
    ``UpstreamChanged`` listing them, before any named entry is refreshed. Refreshed
    files are staged beside the cache and moved into it only after the lockfile is
    saved, so a run that fails for any reason leaves the lockfile as it was and no
    cached file holding bytes it does not pin (ADR 0031). An entry
    pinning byte ranges re-issues exactly those ranges against the pinned ETag, so
    a republished object is reported as drift rather than silently re-resolved.

    When ``USDATA_MIRROR_URL`` names a mirror, an entry whose pinned URL no longer
    reproduces its pin is fetched from ``<mirror>/sha256/<checksum>`` instead and
    verified against the same pin; the result lists it under ``mirrored`` and its
    sidecar records the mirror object. Only an entry the mirror cannot supply is
    drift. See ADR 0030.

    A source whose credentials are unset is never asked. An entry the cache
    cannot supply comes from the mirror instead, listed under ``mirrored`` and
    ``unchecked``, and ``MissingCredentials`` is raised only when the mirror
    cannot supply it either. Every file restored before that matches its pin.
    Updating an entry always asks its source, so a missing credential for an
    ``update`` selection is raised before anything is fetched. See ADR 0039.
    """
    reg = registry or default_registry()
    manifest_path = Path(manifest_path)
    root = None if root is None else Path(root)
    lock_path = lockfile_path(manifest_path)
    lock = Lockfile.load(lock_path)
    _check_manifest(manifest_path, lock)
    selected = _selected(lock, update)
    _progress.batch([entry.provenance.size for entry in lock.assets])
    adapters: dict[str, Provider] = {}
    restored: dict[int, _Restored] = {}
    drift: list[Drift] = []
    with ExitStack() as stack:

        def adapter_for(dataset: Dataset) -> Provider:
            if dataset.id not in adapters:
                adapters[dataset.id] = stack.enter_context(load_adapter(dataset))
            return adapters[dataset.id]

        # A refresh must ask its source, so its credentials are checked before any fetch.
        for entry in lock.assets:
            if entry.asset.id in selected:
                adapter_for(reg.get(entry.asset.dataset_id))
        base = mirror.mirror_url()
        mirrored_from = None if base is None else (base, stack.enter_context(http.client()))
        staging = _staging(root, stack) if selected else None
        # Pinned entries go first. A refresh accepts whatever upstream serves, so it can
        # never drift; holding it back means a run that fails on drift has fetched nothing
        # it would have to throw away.
        refreshed: dict[str, _Restored] = {}
        for refresh in (False, True):
            for index, entry in enumerate(lock.assets):
                if (entry.asset.id in selected) is not refresh:
                    continue
                if (earlier := refreshed.get(entry.asset.id)) is not None and earlier.staged:
                    # Sources sharing an asset share its one refresh, so they share one pin.
                    restored[index] = _repinned(entry, earlier.item, earlier.staged)
                    continue
                outcome = _restore_entry(
                    entry,
                    reg.get(entry.asset.dataset_id),
                    root=root,
                    staging=staging if refresh else None,
                    adapter_for=adapter_for,
                    mirrored_from=mirrored_from,
                )
                if refresh and isinstance(outcome, _Restored):
                    refreshed[entry.asset.id] = outcome
                if isinstance(outcome, Drift):
                    drift.append(outcome)
                else:
                    restored[index] = outcome
            if drift:
                raise UpstreamChanged(drift)
        outcomes = [restored[index] for index in sorted(restored)]  # back in lockfile order
        updated = [outcome.entry.asset.id for outcome in outcomes if outcome.updated]
        # The lockfile moves first. A crash before the files follow leaves a stale cache,
        # which the next restore repairs; the other order leaves bytes that nothing pins.
        if updated:
            lock = lock.model_copy(update={"assets": [outcome.entry for outcome in outcomes]})
            lock.save(lock_path)
        _commit_staged(
            (outcome.staged, outcome.item.path) for outcome in outcomes if outcome.staged
        )
    return PullResult(
        lockfile=lock,
        lockfile_path=lock_path,
        fetched=[outcome.item for outcome in outcomes],
        from_lockfile=True,
        updated=updated,
        mirrored=[outcome.entry.asset.id for outcome in outcomes if outcome.mirrored],
        unchecked=[outcome.entry.asset.id for outcome in outcomes if outcome.unchecked],
        by_source=_by_source((outcome.entry, outcome.item) for outcome in outcomes),
    )


STAGING_DIR = ".staging"
"""Directory under the cache root where refreshed files wait to be committed."""


def _staging(root: Path | None, stack: ExitStack) -> Path:
    """A staging root inside the cache, removed with whatever it still holds when ``stack`` exits.

    It sits under the cache root so that committing a file is a rename on one
    filesystem, and its name cannot be a provider's, so nothing that walks the
    cache as ``<provider>/<name>/<asset id>`` mistakes a staged file for a cached one.
    """
    parent = (root or cache_dir()).expanduser() / STAGING_DIR
    parent.mkdir(parents=True, exist_ok=True)
    return Path(stack.enter_context(TemporaryDirectory(dir=parent)))


def _commit_staged(moves: Iterable[tuple[Path, Path]]) -> None:
    """Move each staged file to its home in the cache, data before sidecar as a fetch writes them.

    Sources that resolve to the same asset stage it at the same path, so each
    staged file is moved once.
    """
    for staged, home in dict(moves).items():
        home.parent.mkdir(parents=True, exist_ok=True)
        staged.replace(home)
        provenance.sidecar_path(staged).replace(provenance.sidecar_path(home))


@dataclass(frozen=True)
class _Restored:
    """One lockfile entry brought back: the entry to pin from now on, and its file."""

    entry: LockedAsset
    item: FetchedAsset
    updated: bool = False
    mirrored: bool = False
    unchecked: bool = False
    """Mirrored without asking the source, whose credentials are unset."""
    staged: Path | None = None
    """Where the file waits until the run commits; ``item.path`` is where it will live."""


def _restore_entry(
    entry: LockedAsset,
    dataset: Dataset,
    *,
    root: Path | None,
    staging: Path | None,
    adapter_for: Callable[[Dataset], Provider],
    mirrored_from: tuple[str, httpx.Client] | None,
) -> _Restored | Drift:
    """Bring back one lockfile entry, or say how it drifted; the lockfile is not touched here.

    An entry takes the first of four paths that applies: given a ``staging``
    root, it is refreshed there with whatever upstream serves now; its cached
    file still matches the pin; the pinned URL reproduces the pin; or the mirror
    supplies the pinned bytes. Only a refresh is staged, because every other
    path writes bytes the lockfile already pins. An adapter is opened only for
    an entry that needs a fetch, and when its source's credentials are unset the
    mirror is the only path left.
    """
    path = asset_path(entry.asset, root)
    if staging is not None:
        return _refresh_entry(entry, dataset, adapter_for(dataset), path, staging)
    if path.is_file():
        _progress.emit(_progress.AssetProgress(entry.asset.id, "start", entry.provenance.size))
        if sha256_file(path) == entry.provenance.checksum:
            provenance.write(entry.provenance, path)
            _progress.emit(_progress.AssetProgress(entry.asset.id, "cached", entry.provenance.size))
            item = FetchedAsset(
                asset=entry.asset, path=path, provenance=entry.provenance, from_cache=True
            )
            return _Restored(entry, item)
    try:
        adapter = adapter_for(dataset)
    except MissingCredentials as missing:
        if mirrored_from is None:
            raise
        item, reason = _restore_from_mirror(entry, path, *mirrored_from)
        if item is None:
            note = f"the mirror could not restore {entry.asset.id} either ({reason})"
            raise MissingCredentials(dataset, missing.missing, note) from None
        return _Restored(entry, item, mirrored=True, unchecked=True)
    pinned = entry.asset.model_copy(update={"checksum": entry.provenance.checksum})
    try:
        item = _fetch_asset(
            dataset, pinned, adapter, root=root, force=True, pinned=entry.provenance
        )
    except (ChecksumMismatch, RangeNotHonored, httpx.HTTPStatusError) as error:
        problem = _unreproduced(error)
        if problem is None:
            raise
        if mirrored_from is not None:
            item, reason = _restore_from_mirror(entry, path, *mirrored_from)
            if item is not None:
                return _Restored(entry, item, mirrored=True)
            problem = f"{problem}; {reason}"
        return Drift(
            asset_id=entry.asset.id, dataset_id=entry.asset.dataset_id, path=path, problem=problem
        )
    return _Restored(entry, item)


GONE = frozenset({404, 410})
"""Statuses that say the pinned object is no longer served, rather than that a request failed."""


def _unreproduced(error: Exception) -> str | None:
    """How a pinned URL failed to reproduce its pin, or None when the failure says nothing of it.

    Different bytes, an object that is gone, and a refused range request all
    mean the pin cannot be had from its source, so each is drift the mirror may
    repair (ADR 0030). Any other failure, such as a server error, is raised.
    """
    # A republished object refuses the pinned ETag, which is drift by another name.
    if isinstance(error, ChecksumMismatch | ObjectChanged):
        return "upstream changed"
    if isinstance(error, RangeNotHonored):
        return "range refused"
    if isinstance(error, httpx.HTTPStatusError) and error.response.status_code in GONE:
        return f"gone upstream ({error.response.status_code})"
    return None


def _refresh_entry(
    entry: LockedAsset, dataset: Dataset, adapter: Provider, path: Path, staging: Path
) -> _Restored:
    """Fetch an entry unpinned into ``staging``, so whatever upstream serves can become the pin.

    The cache is not touched here. The result names ``path`` as the file's home
    and the staged copy that ``_commit_staged`` moves there once the run succeeds.
    """
    unpinned = entry.asset.model_copy(update={"checksum": None})
    try:
        staged = _fetch_asset(
            dataset, unpinned, adapter, root=staging, force=True, pinned=entry.provenance
        )
    except ObjectChanged as error:
        # Pinned byte ranges are only valid for the pinned object; new ones need its new index.
        raise ObjectChanged(
            f"{entry.asset.id} pins byte ranges of an object that was republished, so update "
            "cannot refresh it; pull with force to re-resolve its source"
        ) from error
    return _repinned(entry, staged.model_copy(update={"path": path}), staged.path)


def _repinned(entry: LockedAsset, item: FetchedAsset, staged: Path) -> _Restored:
    """A refreshed file as ``entry``'s outcome: its pin kept for the same bytes, else rewritten.

    Entries that share an asset are refreshed by one fetch, and each is pinned
    from it here, so every entry for the asset pins the bytes the run commits.
    """
    if item.provenance.checksum == entry.provenance.checksum:
        # Same bytes: keep the original pin and record.
        return _Restored(entry, item, staged=staged)
    pinned = item.asset.model_copy(update={"checksum": item.provenance.checksum})
    repinned = LockedAsset(asset=pinned, provenance=item.provenance, source=entry.source)
    return _Restored(repinned, item, updated=True, staged=staged)


def _restore_from_mirror(
    entry: LockedAsset, path: Path, base: str, client: httpx.Client
) -> tuple[FetchedAsset | None, str]:
    """Fetch one pinned entry from the mirror, or say why the mirror could not supply it.

    The pin is unchanged either way. On success the sidecar written beside the
    file is the pinned record plus the mirror object that served it and a new
    retrieval time, so the lockfile still describes the source and the sidecar
    says where these bytes came from.
    """
    _progress.emit(_progress.AssetProgress(entry.asset.id, "start", entry.provenance.size))
    try:
        with staged_path(path) as tmp:
            url = mirror.download(base, entry.provenance.checksum, tmp, client)
    except httpx.HTTPStatusError as error:
        return None, f"not mirrored ({error.response.status_code})"
    except httpx.RequestError as error:
        return None, f"mirror unreachable ({type(error).__name__})"
    except mirror.MirrorMismatch:
        return None, "mirror mismatch"
    prov = entry.provenance.model_copy(update={"retrieved_at": datetime.now(UTC), "mirror": url})
    provenance.write(prov, path)
    _progress.emit(_progress.AssetProgress(entry.asset.id, "fetched", prov.size))
    return FetchedAsset(asset=entry.asset, path=path, provenance=prov, from_cache=False), ""


def pull(
    manifest_path: str | os.PathLike[str],
    *,
    root: str | os.PathLike[str] | None = None,
    force: bool = False,
    registry: Registry | None = None,
    update: Iterable[str] = (),
) -> PullResult:
    """Restore from the lockfile if one exists, otherwise resolve and create it.

    ``update`` names assets or datasets whose pins should follow current upstream
    bytes; it needs an existing lockfile and is exclusive with ``force``.
    """
    manifest_path = Path(manifest_path)
    update = list(update)
    if update and force:
        raise ValueError("update and force are exclusive; force re-resolves every source")
    if force or not lockfile_path(manifest_path).exists():
        if update:
            raise ValueError(f"no lockfile at {lockfile_path(manifest_path)}; pull first")
        return resolve(manifest_path, root=root, registry=registry)
    return restore(manifest_path, root=root, registry=registry, update=update)


def verify(
    manifest_path: str | os.PathLike[str], *, root: str | os.PathLike[str] | None = None
) -> list[Drift]:
    """Check manifest consistency, then compare cached files against the lockfile."""
    manifest_path = Path(manifest_path)
    root = None if root is None else Path(root)
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
    "Plan",
    "PullResult",
    "SourcePlan",
    "UnknownAssets",
    "UnknownDatasets",
    "UpstreamChanged",
    "plan",
    "provenance",
    "pull",
    "resolve",
    "restore",
    "verify",
]
