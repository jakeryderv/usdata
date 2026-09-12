"""Render the dataset registry into the docs.

Outputs live exclusively under docs/generated/catalog/.
Provider access notes, usage guides, indexes, and the roadmap are handwritten.

Run via ``just docs``. ``--check`` renders without writing and exits 1 if any
generated content on disk differs, which is what ``just check`` and CI run.
"""

from __future__ import annotations

import posixpath
import re
import sys
import tomllib
from collections import Counter
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from usdata.models import LATER, Dataset, ProviderInfo, Status
from usdata.registry import Registry, version_key

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
CATALOG_DIR = ROOT / "docs/generated/catalog"
STATUS_ORDER = [Status.AVAILABLE, Status.STUB, Status.PLANNED]
GENERATED_NOTE = (
    "Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand."
)


def _extent(ds: Dataset) -> list[str]:
    parts = []
    if ds.spatial_extent:
        w, south, e, n = ds.spatial_extent.as_tuple()
        parts.append(
            f"- Geographic bounds (WGS84): west {w:g}°, south {south:g}°, east {e:g}°, north {n:g}°"
        )
    if ds.temporal_extent:
        start = ds.temporal_extent.start.date() if ds.temporal_extent.start else "not specified"
        end = ds.temporal_extent.end.date() if ds.temporal_extent.end else "open-ended"
        parts.append(f"- Catalog date range: {start} to {end}")
    return parts or ["- Coverage: not specified in the catalog"]


def _anchor(text: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", text.lower().replace(" ", "-"))


def by_provider(registry: Registry) -> list[tuple[ProviderInfo, list[Dataset]]]:
    """Providers with the most implemented datasets first, then by name; datasets by status."""
    groups: dict[str, list[Dataset]] = {}
    for ds in registry:
        groups.setdefault(ds.provider, []).append(ds)

    def progress(pid: str) -> tuple[int, int, str]:
        counts = Counter(d.status for d in groups[pid])
        return (-counts[Status.AVAILABLE], -counts[Status.STUB], registry.provider(pid).name)

    domain_order = [d.id for d in registry.domains()]

    def dataset_key(d: Dataset) -> tuple[int, int, tuple[int, ...], str]:
        return (
            STATUS_ORDER.index(d.status),
            domain_order.index(d.domain),
            version_key(d.target or d.since or LATER),
            d.id,
        )

    return [
        (registry.provider(pid), sorted(groups[pid], key=dataset_key))
        for pid in sorted(groups, key=progress)
    ]


def availability(ds: Dataset) -> str:
    if ds.status is not Status.AVAILABLE:
        return "Planned"
    if not ds.since or version_key(ds.since) > version_key(PACKAGE_VERSION):
        return "Source only"
    return "Released"


def implementation_version(ds: Dataset) -> str:
    if availability(ds) == "Source only":
        return f"Source only · intended for {ds.since or 'a future release'}"
    return ds.version_label


def summary_table(registry: Registry, link_prefix: str) -> str:
    lines = ["| Provider | Released | Source only | Planned |", "|---|---:|---:|---:|"]
    for info, datasets in by_provider(registry):
        counts = Counter(availability(ds) for ds in datasets)
        lines.append(
            f"| [{info.name}]({link_prefix}{info.id}.md) | {counts['Released']} "
            f"| {counts['Source only']} | {counts['Planned']} |"
        )
    return "\n".join(lines) + "\n"


def cell(text: str) -> str:
    return text.replace("|", "&#124;").replace("\n", " ")


def dataset_table(datasets: list[Dataset], entries: dict[str, CatalogEntry]) -> str:
    lines = [
        "| Dataset | Availability | Files | What gets selected |",
        "|---|---|---|---|",
    ]
    for ds in datasets:
        entry = entries[ds.id]
        anchor = _anchor(ds.id.replace(":", ""))
        lines.append(
            f'| <span id="{anchor}"></span>[{cell(entry.summary)}]({ds.provider}/{ds.name}.md) '
            f"| {availability(ds)} | {cell(', '.join(entry.formats))} | {cell(entry.selection)} |"
        )
    return "\n".join(lines) + "\n"


def planned_block(registry: Registry, datasets: list[Dataset]) -> str:
    if not datasets:
        return "No planned datasets for this provider.\n"
    lines = ["These entries are not implemented; they cannot fetch data.", ""]
    for ds in datasets:
        lines += [
            f"### {ds.id}",
            "",
            f"**{ds.title}** · Planned · {ds.version_label}",
            "",
            ds.description.strip(),
            "",
            f"[Upstream information]({ds.homepage})" if ds.homepage else "",
            f"Domain: {registry.domain(ds.domain).name}.",
            "Adapter scaffold exists; fetching is not implemented."
            if ds.status is Status.STUB
            else "",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def render_roadmap_block(registry: Registry) -> str:
    """Datasets grouped by the version they shipped in or are targeted at."""
    shipped: dict[str, list[Dataset]] = {}
    targeted: dict[str, list[Dataset]] = {}
    for ds in registry:
        if ds.status is Status.AVAILABLE:
            shipped.setdefault(ds.since or LATER, []).append(ds)
        else:
            targeted.setdefault(ds.target or LATER, []).append(ds)

    def group(title: str, datasets: list[Dataset]) -> list[str]:
        out = ["", f"**{title}**", ""]
        for ds in sorted(datasets, key=lambda d: (d.provider, d.id)):
            page = f"{ds.provider}.md#{_anchor(ds.id.replace(':', ''))}"
            out.append(f"- [`{ds.id}`]({page}) {ds.title} · {availability(ds)}")
        return out

    lines = [GENERATED_NOTE, ""]
    lines.append("Move a dataset between phases by editing its `target` in the registry.")
    for v in sorted(targeted, key=version_key):
        lines += group(f"Target {v}" if v != LATER else "Later", targeted[v])
    for v in sorted(shipped, key=version_key, reverse=True):
        title = (
            f"Implemented, unreleased (planned {v})"
            if version_key(v) > version_key(PACKAGE_VERSION)
            else f"Included since {v}"
        )
        lines += group(title, shipped[v])
    return "\n".join(lines) + "\n"


class CatalogEntry(BaseModel):
    """Documentation metadata, validated separately from the SDK dataset model."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    guide: str
    summary: str = Field(min_length=1, max_length=80)
    formats: list[str] = Field(min_length=1)
    selection: str = Field(min_length=1, max_length=160)
    inputs: str = Field(min_length=1, max_length=200)
    reader_extra: str | None
    examples: list[str] = Field(min_length=1)


def catalog_entries(registry: Registry, root: Path = ROOT) -> dict[str, CatalogEntry]:
    raw = yaml.safe_load((root / "src/usdata/data/registry.yaml").read_text())
    entries = {key: CatalogEntry.model_validate(value) for key, value in raw["catalog"].items()}
    known = {ds.id for ds in registry}
    if unknown := entries.keys() - known:
        raise ValueError(f"unknown catalog IDs: {sorted(unknown)}")
    extras = tomllib.loads((root / "pyproject.toml").read_text())["project"][
        "optional-dependencies"
    ]
    guides = set()
    for ds in registry:
        if not all(re.fullmatch(r"[a-z0-9][a-z0-9-]*", part) for part in (ds.provider, ds.name)):
            raise ValueError(
                f"{ds.id}: catalog IDs must use lowercase letters, digits, and hyphens"
            )
        if ds.status is Status.AVAILABLE and ds.id not in entries:
            raise ValueError(f"{ds.id}: implemented datasets require catalog metadata")
    for key, entry in entries.items():
        if registry.get(key).status is not Status.AVAILABLE:
            raise ValueError(f"{key}: usage metadata is only for implemented datasets")
        if entry.reader_extra is not None and entry.reader_extra not in extras:
            raise ValueError(f"{key}: unknown reader extra {entry.reader_extra!r}")
        for example in entry.examples:
            path = Path(example)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not path.is_relative_to("examples")
                or path.suffix not in {".md", ".ipynb"}
                or not (root / path).resolve().is_relative_to(root.resolve())
                or not (root / path).is_file()
            ):
                raise ValueError(f"{key}: example must be an existing document in examples")
        if any(
            not value.strip() or "\n" in value
            for value in [entry.summary, entry.selection, entry.inputs, *entry.formats]
        ):
            raise ValueError(f"{key}: catalog summaries and formats must be nonempty single lines")
        path = Path(entry.guide)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not path.is_relative_to("docs/providers")
            or path.suffix != ".md"
            or not (root / path).resolve().is_relative_to(root.resolve())
            or not (root / path).is_file()
        ):
            raise ValueError(f"{key}: guide must be an existing Markdown file in docs/providers")
        if (root / path).resolve() in guides:
            raise ValueError(f"{key}: each dataset needs its own usage guide")
        guides.add((root / path).resolve())
    return entries


def dataset_path(ds: Dataset) -> Path:
    return Path("docs/generated/catalog") / ds.provider / f"{ds.name}.md"


def usage_link(ds: Dataset, entry: CatalogEntry) -> str:
    relative = posixpath.relpath(entry.guide, dataset_path(ds).parent.as_posix())
    return f"[Usage guide]({relative})."


def render_dataset(registry: Registry, ds: Dataset, entry: CatalogEntry) -> str:
    parent = dataset_path(ds).parent.as_posix()
    examples = ", ".join(
        f"[{Path(path).parent.name.replace('-', ' ')}]"
        f"({posixpath.relpath(Path('docs') / Path(path).with_suffix('.md'), parent)})"
        for path in entry.examples
    )
    reader = (
        f"`usdata[{entry.reader_extra}]` · [Reader guide](../../../reference/readers.md)"
        if entry.reader_extra
        else "Local files; no bundled reader for this format"
    )
    notice = (
        "Install from [source](../../../project.md#source-installation) to use this dataset."
        if availability(ds) == "Source only"
        else f"Included since usdata {ds.since}."
    )
    lines = [
        f"# {entry.summary}",
        "",
        GENERATED_NOTE,
        "",
        f"`{ds.id}` · **{availability(ds)}** · {notice}",
        "",
        f"{ds.title}.",
        "",
        "## At a glance",
        "",
        f"- Files: {', '.join(entry.formats)}",
        f"- Selection: {entry.selection}",
        f"- Required inputs: {entry.inputs}",
        f"- Open locally: {reader}",
        f"- Examples: {examples}",
        "",
        "## Usage and limitations",
        "",
        usage_link(ds, entry),
        "",
        "## Catalog reference",
        "",
        f"- Availability: {implementation_version(ds)}",
        f"- Domain: {registry.domain(ds.domain).name}",
        *_extent(ds),
        "- Coverage varies by station, product, and date; "
        "the range above does not guarantee observations.",
        f"- [Upstream documentation]({ds.homepage})" if ds.homepage else "",
        f"- License: {ds.license or 'not stated'}",
        f"- Transport: `{ds.protocol.value}`",
        f"- Adapter: `{ds.adapter}`",
        "",
        f"[All {registry.provider(ds.provider).name} datasets](../{ds.provider}.md).",
        "",
    ]
    return "\n".join(lines)


AVAILABILITY_NOTE = (
    f"**Released** is included in usdata {PACKAGE_VERSION}. **Source only** is implemented "
    "in this checkout and requires a source installation. **Planned** cannot fetch data yet."
    "\n"
)


def render_all(registry: Registry) -> dict[Path, str]:
    """Generate only inside the owned catalog directory; never rewrite prose."""
    entries = catalog_entries(registry)
    implemented = [
        ds
        for _, datasets in by_provider(registry)
        for ds in datasets
        if ds.status is Status.AVAILABLE
    ]
    outputs = {
        CATALOG_DIR / "index.md": "# Find a dataset\n\n"
        + GENERATED_NOTE
        + "\n\n"
        + AVAILABILITY_NOTE
        + "\n## Implemented datasets\n\n"
        + dataset_table(implemented, entries)
        + "\n## Browse by provider\n\n"
        + summary_table(registry, "")
        + "\nPlanned entries are listed separately on each provider page. "
        "See [versions and targets](versions.md) for future work.\n"
    }
    for info, datasets in by_provider(registry):
        available = [ds for ds in datasets if ds.status is Status.AVAILABLE]
        planned = [ds for ds in datasets if ds.status is not Status.AVAILABLE]
        outputs[CATALOG_DIR / f"{info.id}.md"] = (
            f"# {info.name} datasets\n\n{GENERATED_NOTE}\n\n"
            f"[Provider access notes](../../providers/{info.id}.md).\n\n"
            + AVAILABILITY_NOTE
            + "\n## Implemented datasets\n\n"
            + (dataset_table(available, entries) if available else "None implemented yet.\n")
            + "\n## Planned datasets\n\n"
            + planned_block(registry, planned)
        )
        for ds in available:
            outputs[ROOT / dataset_path(ds)] = render_dataset(registry, ds, entries[ds.id])
    outputs[CATALOG_DIR / "versions.md"] = (
        "# Dataset versions and targets\n\n" + render_roadmap_block(registry)
    )
    return outputs


def sync(outputs: dict[Path, str], *, check: bool) -> list[Path]:
    if any(not path.resolve().is_relative_to(CATALOG_DIR.resolve()) for path in outputs):
        raise ValueError("generated outputs must stay inside docs/generated/catalog")
    obsolete = set(CATALOG_DIR.rglob("*.md")) - outputs.keys()
    stale = [p for p, text in outputs.items() if not p.exists() or p.read_text() != text]
    if not check:
        for path in obsolete:
            # Refuse to remove unexpected handwritten content even in the owned directory.
            if GENERATED_NOTE not in path.read_text():
                raise ValueError(f"refusing to remove unrecognized file: {path}")
        for path in obsolete:
            path.unlink()
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    return sorted(set(stale) | obsolete)


if __name__ == "__main__":
    outputs = render_all(Registry.bundled())
    stale = sync(outputs, check="--check" in sys.argv)
    if "--check" in sys.argv and stale:
        names = ", ".join(p.relative_to(ROOT).as_posix() for p in stale)
        sys.exit(f"generated docs are stale ({names}): run 'just docs' and commit")
    print("generated catalog is current")
