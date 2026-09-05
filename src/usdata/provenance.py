"""Create and persist provenance records next to cached files."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from usdata import __version__
from usdata.cache import sha256_file
from usdata.models import Asset, Dataset, Provenance

SIDECAR_SUFFIX = ".provenance.json"


def record(dataset: Dataset, asset: Asset, path: Path) -> Provenance:
    """Build a provenance record for a file that was just fetched to ``path``."""
    return Provenance(
        dataset_id=dataset.id,
        provider=dataset.provider,
        source_url=asset.href,
        retrieved_at=datetime.now(UTC),
        checksum=sha256_file(path),
        size=path.stat().st_size,
        license=dataset.license,
        usdata_version=__version__,
    )


def sidecar_path(path: Path) -> Path:
    """The provenance JSON file that sits beside a cached file."""
    return path.with_name(path.name + SIDECAR_SUFFIX)


def write(prov: Provenance, path: Path) -> Path:
    """Write a provenance record beside ``path`` and return the sidecar path."""
    out = sidecar_path(path)
    out.write_text(prov.model_dump_json(indent=2))
    return out


def read(path: Path) -> Provenance:
    """Load the provenance record stored beside ``path``."""
    return Provenance.model_validate_json(sidecar_path(path).read_text())
