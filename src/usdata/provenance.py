"""Create and persist provenance records next to cached files."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from usdata import __version__
from usdata._files import atomic_write_text
from usdata.cache import sha256_file
from usdata.models import Asset, Dataset, PartialFetch, Provenance

SIDECAR_SUFFIX = ".provenance.json"


def record(
    dataset: Dataset, asset: Asset, path: Path, partial: PartialFetch | None = None
) -> Provenance:
    """Build a provenance record for a file that was just fetched to ``path``.

    Args:
        dataset: The registry entry the asset belongs to.
        asset: The asset that was fetched, whose href is the recorded source URL.
        path: The file that arrived, which is hashed and measured here.
        partial: The byte ranges a partial fetch concatenated, when it was one.
            Its index, ranges, and object identity are recorded alongside the
            checksum of the local file, which still covers exactly these bytes.

    Returns:
        The record to write beside ``path``.
    """
    return Provenance(
        dataset_id=dataset.id,
        provider=dataset.provider,
        source_url=asset.href,
        retrieved_at=datetime.now(UTC),
        checksum=sha256_file(path),
        size=path.stat().st_size,
        license=dataset.license,
        usdata_version=__version__,
        transformations=[] if partial is None else [partial.describe()],
        index_url=None if partial is None else partial.index_url,
        index_checksum=None if partial is None else partial.index_checksum,
        ranges=[] if partial is None else list(partial.ranges),
        object_size=None if partial is None else partial.object_size,
        object_etag=None if partial is None else partial.object_etag,
    )


def sidecar_path(path: Path) -> Path:
    """The provenance JSON file that sits beside a cached file."""
    return path.with_name(path.name + SIDECAR_SUFFIX)


def write(prov: Provenance, path: Path) -> Path:
    """Write a provenance record beside ``path`` and return the sidecar path."""
    out = sidecar_path(path)
    atomic_write_text(out, prov.model_dump_json(indent=2))
    return out


def read(path: Path) -> Provenance:
    """Load the provenance record stored beside ``path``."""
    return Provenance.model_validate_json(sidecar_path(path).read_text())
