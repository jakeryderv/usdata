"""Inspect and prune the local cache: what it holds, how large it is, what to drop.

Everything here reads the cache layout that :mod:`usdata.cache` writes,
``<root>/<provider>/<name>/<asset id>`` with a provenance sidecar beside each
data file. Only :func:`prune` deletes, and it removes a data file together with
its sidecar so neither outlives the other.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from usdata import provenance
from usdata._files import is_temporary
from usdata.cache import asset_path, cache_dir
from usdata.manifest import Lockfile, lockfile_path
from usdata.models import AwareUTC, Provenance, as_utc
from usdata.provenance import SIDECAR_SUFFIX

MANIFEST_GLOBS = ("*.yaml", "*.yml")
"""Manifest filenames whose ``*.lock.json`` neighbours pin cached files."""

_SHORT = re.compile(r"(?P<count>\d+)(?P<unit>[dh])")
_ISO = re.compile(
    r"P(?:(?P<weeks>\d+)W)?(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?"
)


class CacheEntry(BaseModel):
    """One cached data file and what its provenance sidecar says about it."""

    dataset_id: str
    asset_id: str
    path: Path
    size: int = Field(ge=0, description="Bytes of the data file, excluding its sidecar")
    modified_at: AwareUTC = Field(description="Filesystem modification time, in UTC")
    retrieved_at: AwareUTC | None = Field(
        default=None,
        description="When the sidecar says the file was fetched; unset without a readable sidecar",
    )

    @property
    def recorded(self) -> bool:
        """Whether a readable provenance sidecar sits beside the file."""
        return self.retrieved_at is not None

    def age(self, now: datetime) -> timedelta:
        """How old the file is at ``now``, by its sidecar and otherwise its mtime."""
        return now - (self.retrieved_at or self.modified_at)


def parse_duration(text: str) -> timedelta:
    """Parse an age such as ``30d``, ``12h``, or the ISO 8601 duration ``P30D``.

    Args:
        text: ``Nd``, ``Nh``, or an ISO 8601 duration of weeks, days, hours,
            minutes, and seconds. Years and months are rejected because their
            length depends on the calendar date they are measured from.

    Returns:
        The duration as a positive ``timedelta``.

    Raises:
        ValueError: The text is not one of those forms, or is not positive.
    """
    value = text.strip()
    if short := _SHORT.fullmatch(value):
        unit = {"d": "days", "h": "hours"}[short["unit"]]
        duration = timedelta(**{unit: int(short["count"])})
    elif iso := _ISO.fullmatch(value.upper()):
        duration = timedelta(**{name: int(raw) for name, raw in iso.groupdict().items() if raw})
    else:
        raise ValueError(f"invalid duration {text!r}: use 30d, 12h, or an ISO 8601 duration")
    if duration <= timedelta(0):
        raise ValueError(f"duration must be positive, got {text!r}")
    return duration


def entries(root: Path | None = None) -> list[CacheEntry]:
    """Every cached data file, sorted by dataset id and then asset id.

    Args:
        root: Cache root to walk; the configured cache directory when omitted.

    Returns:
        One entry per file at ``<root>/<provider>/<name>/<asset id>``. A file
        with no readable sidecar is still listed, as unrecorded, with its
        dataset id taken from the directories it sits in. Sidecars themselves,
        temporary files a download or a killed run left, the staging directory,
        and files at any other depth, are skipped.
    """
    base = _root(root)
    if not base.is_dir():
        return []
    found = [
        _entry(path)
        for provider in _subdirectories(base)
        # No provider id starts with a dot; the staging directory does.
        if not provider.name.startswith(".")
        for name in _subdirectories(provider)
        for path in sorted(name.iterdir())
        if path.is_file() and not path.name.endswith(SIDECAR_SUFFIX) and not is_temporary(path)
    ]
    return sorted(found, key=lambda entry: (entry.dataset_id, entry.asset_id))


def total_size(root: Path | None = None) -> int:
    """Total bytes of the cached data files, not counting provenance sidecars.

    Args:
        root: Cache root to walk; the configured cache directory when omitted.

    Returns:
        The sum of every entry's size.
    """
    return sum(entry.size for entry in entries(root))


def candidates(
    root: Path | None = None,
    *,
    older_than: timedelta | None = None,
    dataset: str | None = None,
    now: datetime | None = None,
) -> list[CacheEntry]:
    """The entries these filters select, before any pinning is applied.

    Args:
        root: Cache root to walk; the configured cache directory when omitted.
        older_than: Keep entries younger than this age. Unfiltered when None.
        dataset: Keep only entries of this dataset id. Unfiltered when None.
        now: The moment ages are measured from; the current UTC time when omitted.
            A naive value means UTC.

    Returns:
        The matching entries, in the order :func:`entries` returns them.
    """
    moment = datetime.now(UTC) if now is None else as_utc(now)
    return [
        entry
        for entry in entries(root)
        if (dataset is None or entry.dataset_id == dataset)
        and (older_than is None or entry.age(moment) >= older_than)
    ]


def prune(
    root: Path | None = None,
    *,
    older_than: timedelta | None = None,
    dataset: str | None = None,
    pinned: frozenset[Path] = frozenset(),
    dry_run: bool = False,
    now: datetime | None = None,
) -> list[CacheEntry]:
    """Delete the cached files these filters select, keeping every pinned path.

    Each data file is removed with its provenance sidecar, in that order, so a
    sidecar is never left describing a file that is gone.

    Args:
        root: Cache root to prune; the configured cache directory when omitted.
        older_than: Remove only entries at least this old, by sidecar or mtime.
        dataset: Remove only entries of this dataset id.
        pinned: Cache paths to keep whatever the filters select, usually from
            :func:`pinned_paths`.
        dry_run: Select and return, but delete nothing.
        now: The moment ages are measured from; the current UTC time when omitted.

    Returns:
        The entries that were removed, or that would be removed under ``dry_run``.

    Raises:
        OSError: A file could not be deleted. Earlier deletions stand.
    """
    removed = [
        entry
        for entry in candidates(root, older_than=older_than, dataset=dataset, now=now)
        if entry.path not in pinned
    ]
    if not dry_run:
        for entry in removed:
            entry.path.unlink(missing_ok=True)
            provenance.sidecar_path(entry.path).unlink(missing_ok=True)
    return removed


def pinned_paths(directory: Path | None = None, root: Path | None = None) -> set[Path]:
    """Cache paths pinned by the lockfiles beside the manifests in a directory.

    Args:
        directory: Where to look for ``*.yaml`` and ``*.yml`` manifests; the
            current directory when omitted. A manifest with no
            ``<stem>.lock.json`` beside it pins nothing.
        root: Cache root the pinned assets are placed in; the configured cache
            directory when omitted.

    Returns:
        The cache path of every asset those lockfiles pin.

    Raises:
        ValueError: A lockfile could not be read, or pins an asset whose ids
            cannot be placed in the cache.
    """
    base = directory or Path()
    paths: set[Path] = set()
    for manifest in sorted({path for glob in MANIFEST_GLOBS for path in base.glob(glob)}):
        lock = lockfile_path(manifest)
        if not lock.is_file():
            continue
        try:
            locked = Lockfile.load(lock)
        except (OSError, ValidationError) as e:
            raise ValueError(f"cannot read lockfile {lock}: {e}") from e
        paths.update(asset_path(entry.asset, root) for entry in locked.assets)
    return paths


def _root(root: Path | None) -> Path:
    """The cache root as an absolute path, matching what ``asset_path`` builds."""
    base = (root or cache_dir()).expanduser()
    return base.resolve() if base.exists() else base


def _subdirectories(path: Path) -> list[Path]:
    """The directories directly inside ``path``, sorted by name."""
    return sorted(child for child in path.iterdir() if child.is_dir())


def _entry(path: Path) -> CacheEntry:
    """Describe one cached data file, from its sidecar where there is one."""
    stat = path.stat()
    record = _sidecar(path)
    return CacheEntry(
        dataset_id=record.dataset_id if record else f"{path.parent.parent.name}:{path.parent.name}",
        asset_id=path.name,
        path=path,
        size=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime, UTC),
        retrieved_at=record.retrieved_at if record else None,
    )


def _sidecar(path: Path) -> Provenance | None:
    """The provenance beside a cached file, or None when it is absent or unreadable."""
    try:
        return provenance.read(path)
    except (OSError, ValidationError):
        return None
