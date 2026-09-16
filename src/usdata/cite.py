"""Citations for a dataset entry, or for the inputs a manifest's lockfile pins.

Citations are derived, never stored: they read the registry entry and, for a
manifest, the lockfile that a pull already wrote. Nothing here writes anything.
Rendering is plain text for a methods section or BibTeX for a bibliography.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, Field

from usdata.manifest import LockedAsset, Lockfile, lockfile_path
from usdata.models import Dataset, ProviderInfo, TimeRange
from usdata.pull import _check_manifest
from usdata.registry import Registry, default_registry

ACCESSED_VIA = "accessed via usdata"
"""Tail of the fallback citation used when a registry entry states none."""

_NOT_KEY = re.compile(r"[^A-Za-z0-9]+")
_BIBTEX_SPECIAL = re.compile(r"([&%$#_])")


class Citation(BaseModel):
    """How to cite one dataset, plus what a lockfile pins of it when there is one.

    The retrieval fields are empty for a citation built from a registry entry
    alone; they are filled only when the citation comes from a lockfile.
    """

    dataset_id: str
    title: str
    text: str = Field(description="The entry's citation, or an agency and title fallback")
    homepage: str | None = None
    license: str | None = None
    terms: str | None = None
    retrieved: TimeRange | None = Field(
        default=None, description="First and last retrieval time among the pinned assets"
    )
    asset_count: int = Field(default=0, ge=0, description="Pinned assets, every one checksummed")
    total_bytes: int = Field(default=0, ge=0, description="Bytes across the pinned assets")
    usdata_version: str | None = Field(
        default=None, description="Version of usdata that wrote the lockfile"
    )
    sources: list[str] = Field(
        default_factory=list, description="Keys of the manifest sources that pinned the assets"
    )


def cite_dataset(dataset: Dataset, *, registry: Registry | None = None) -> Citation:
    """Build the citation for one registry entry.

    Args:
        dataset: The entry to cite.
        registry: Registry supplying the agency name and homepage behind the
            entry's provider id. The bundled registry by default.

    Returns:
        A citation carrying the entry's own citation text where it has one, and
        '<Agency>, <Title>, accessed via usdata' where it does not.
    """
    provider = _provider(dataset.provider, registry or default_registry())
    return Citation(
        dataset_id=dataset.id,
        title=dataset.title,
        text=dataset.citation or f"{provider.name}, {dataset.title}, {ACCESSED_VIA}",
        homepage=dataset.homepage or provider.homepage,
        license=dataset.license,
        terms=dataset.terms,
    )


def cite_lockfile(manifest_path: Path, registry: Registry | None = None) -> list[Citation]:
    """Cite every dataset a manifest's lockfile pins, one citation per dataset.

    Args:
        manifest_path: The manifest whose lockfile records what was fetched.
        registry: Registry the pinned dataset ids are looked up in. The bundled
            registry by default.

    Returns:
        One citation per distinct dataset id, in lockfile order, each carrying
        the retrieval range, asset count, total bytes, pinning version, and
        manifest source keys of that dataset's pinned assets.

    Raises:
        ManifestChanged: The manifest was edited after the lockfile was written.
        DatasetNotFound: The lockfile pins a dataset the registry does not know.
    """
    reg = registry or default_registry()
    lock = Lockfile.load(lockfile_path(manifest_path))
    _check_manifest(manifest_path, lock)
    grouped: dict[str, list[LockedAsset]] = {}
    for entry in lock.assets:
        grouped.setdefault(entry.asset.dataset_id, []).append(entry)
    return [
        _cite_pinned(reg, dataset_id, entries, lock.usdata_version)
        for dataset_id, entries in grouped.items()
    ]


def render_text(citations: Iterable[Citation]) -> str:
    """Render citations as plain text, one labelled block per dataset."""
    return "\n\n".join("\n".join(_text_lines(citation)) for citation in citations)


def render_bibtex(citations: Iterable[Citation]) -> str:
    """Render citations as BibTeX ``@misc`` entries, one per dataset."""
    return "\n\n".join(_bibtex_entry(citation) for citation in citations)


def _provider(provider_id: str, registry: Registry) -> ProviderInfo:
    """Display information for a provider id, upper-cased where the registry has none."""
    try:
        return registry.provider(provider_id)
    except KeyError:
        return ProviderInfo(id=provider_id, name=provider_id.upper())


def _cite_pinned(
    registry: Registry, dataset_id: str, entries: list[LockedAsset], usdata_version: str
) -> Citation:
    """One dataset's citation, extended with what its lockfile entries record."""
    times = [entry.provenance.retrieved_at for entry in entries]
    base = cite_dataset(registry.get(dataset_id), registry=registry)
    return base.model_copy(
        update={
            "license": base.license or entries[0].provenance.license,
            "retrieved": TimeRange(start=min(times), end=max(times)),
            "asset_count": len(entries),
            "total_bytes": sum(entry.provenance.size for entry in entries),
            "usdata_version": usdata_version,
            "sources": list(dict.fromkeys(entry.source for entry in entries if entry.source)),
        }
    )


def _retrieval(citation: Citation, retrieved: TimeRange) -> str:
    """The retrieval dates, checksummed asset count, size, and pinning version."""
    bounds = [moment.date().isoformat() for moment in (retrieved.start, retrieved.end) if moment]
    dates = " through ".join(dict.fromkeys(bounds)) or "an unrecorded date"
    assets = "asset" if citation.asset_count == 1 else "assets"
    version = f" by usdata {citation.usdata_version}" if citation.usdata_version else ""
    return (
        f"{dates}; {citation.asset_count} checksummed {assets} "
        f"({citation.total_bytes:,} bytes) pinned{version}"
    )


def _text_lines(citation: Citation) -> list[str]:
    """The dataset id, its citation text, and every field that is set."""
    lines = [citation.dataset_id, f"  {citation.text}"]
    labelled = (
        ("homepage", citation.homepage),
        ("license", citation.license),
        ("terms", citation.terms),
    )
    lines.extend(f"  {label}: {value}" for label, value in labelled if value)
    if (retrieved := citation.retrieved) is not None:
        lines.append(f"  retrieved: {_retrieval(citation, retrieved)}")
    if citation.sources:
        lines.append(f"  sources: {', '.join(citation.sources)}")
    return lines


def _bibtex_entry(citation: Citation) -> str:
    """One ``@misc`` entry: the title, the citation text, what was pinned, and a url."""
    fields = [
        ("title", _escape(citation.title)),
        ("howpublished", _escape(citation.text)),
    ]
    if (retrieved := citation.retrieved) is not None:
        fields.append(("note", _escape(f"Retrieved {_retrieval(citation, retrieved)}")))
    if url := citation.homepage or citation.terms:
        fields.append(("url", url))  # URLs are verbatim: BibTeX escapes break them.
    width = max(len(name) for name, _ in fields)
    body = "".join(f"  {name:<{width}} = {{{value}}},\n" for name, value in fields)
    return f"@misc{{{_NOT_KEY.sub('-', citation.dataset_id)},\n{body}}}"


def _escape(value: str) -> str:
    """Backslash-escape the BibTeX specials a registry citation can contain."""
    return _BIBTEX_SPECIAL.sub(r"\\\1", value)


__all__ = [
    "ACCESSED_VIA",
    "Citation",
    "cite_dataset",
    "cite_lockfile",
    "render_bibtex",
    "render_text",
]
