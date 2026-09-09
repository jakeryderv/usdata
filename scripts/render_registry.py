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
from pydantic import BaseModel, ConfigDict

from usdata.models import LATER, Dataset, ProviderInfo, Status
from usdata.registry import Registry, version_key

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
CATALOG_DIR = ROOT / "docs/generated/catalog"
STATUS_ORDER = [Status.AVAILABLE, Status.STUB, Status.PLANNED]
GENERATED_NOTE = (
    "Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand."
)


def _caps(ds: Dataset) -> str:
    on = [k.replace("_subset", "") for k, v in ds.capabilities.model_dump().items() if v]
    return ", ".join(on) or "none"


def _extent(ds: Dataset) -> str:
    parts = []
    if ds.spatial_extent:
        w, s, e, n = ds.spatial_extent.as_tuple()
        parts.append(f"{w:g}, {s:g}, {e:g}, {n:g}")
    if ds.temporal_extent:
        start = ds.temporal_extent.start.date() if ds.temporal_extent.start else "…"
        end = ds.temporal_extent.end.date() if ds.temporal_extent.end else "present"
        parts.append(f"{start} to {end}")
    return "; ".join(parts) or "not stated"


def _anchor(text: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", text.lower().replace(" ", "-"))


def _first_sentence(text: str) -> str:
    return text.strip().split(". ")[0].rstrip(".") + "."


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
            domain_order.index(d.domain),
            STATUS_ORDER.index(d.status),
            version_key(d.target or d.since or LATER),
            d.id,
        )

    return [
        (registry.provider(pid), sorted(groups[pid], key=dataset_key))
        for pid in sorted(groups, key=progress)
    ]


def summary_table(registry: Registry, link_prefix: str) -> str:
    """Per-provider counts; ``link_prefix`` is the relative path to docs/providers/."""
    nxt = registry.next_target()
    lines = [
        f"| Provider | Available | Stub | Planned | Next up ({nxt or 'unassigned'}) | Datasets |",
        "|---|---:|---:|---:|---|---|",
    ]
    for info, datasets in by_provider(registry):
        counts = Counter(d.status for d in datasets)
        names = ", ".join(
            f"`{d.name}`" if d.status is Status.AVAILABLE else f"_{d.name}_"
            for d in datasets
            if d.status is not Status.PLANNED
        )
        if counts[Status.PLANNED]:
            names = f"{names}, " if names else ""
            names += f"+{counts[Status.PLANNED]} planned"
        next_up = (
            ", ".join(f"`{d.name}`" for d in datasets if nxt is not None and d.target == nxt) or "—"
        )
        lines.append(
            f"| [{info.name}]({link_prefix}{info.id}.md) "
            f"| {counts[Status.AVAILABLE]} | {counts[Status.STUB]} | {counts[Status.PLANNED]} "
            f"| {next_up} | {names} |"
        )
    return "\n".join(lines) + "\n"


def implementation_version(ds: Dataset) -> str:
    """Distinguish upcoming implementations from the declared package version."""
    if ds.since and version_key(ds.since) > version_key(PACKAGE_VERSION):
        return f"unreleased; planned {ds.since}"
    return ds.version_label


def render_datasets_block(registry: Registry, datasets: list[Dataset]) -> str:
    """Generated block for one provider page: table, then details."""
    lines = [
        GENERATED_NOTE,
        "",
        "| Dataset | Domain | Status | Version | Description | Protocol |",
        "|---|---|---|---|---|---|",
    ]
    for ds in datasets:
        link = f"[`{ds.id}`](#{_anchor(ds.id.replace(':', ''))})"
        lines.append(
            f"| {link} | {registry.domain(ds.domain).name} | {ds.status.value} "
            f"| {implementation_version(ds)} | {_first_sentence(ds.description)} "
            f"| {ds.protocol.value} |"
        )
    for ds in datasets:
        lines += [
            "",
            f"### {ds.id}",
            "",
            f"**{ds.title}** · {ds.status.value} · {implementation_version(ds)}",
            "",
            ds.description.strip(),
            "",
            f"- Domain: {registry.domain(ds.domain).name}",
            f"- Server-side subsetting: {_caps(ds)}",
            f"- Homepage: {ds.homepage or 'not stated'}",
            f"- License: {ds.license or 'not stated'}",
            f"- Extent: {_extent(ds)}",
            f"- Keywords: {', '.join(ds.keywords) or 'none'}",
            f"- Adapter: `{ds.adapter}`" if ds.adapter else "- Adapter: none yet",
        ]
    return "\n".join(lines) + "\n"


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
            out.append(f"- [`{ds.id}`]({page}) {ds.title} · {ds.status.value}")
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


def catalog_entries(registry: Registry, root: Path = ROOT) -> dict[str, CatalogEntry]:
    raw = yaml.safe_load((root / "src/usdata/data/registry.yaml").read_text())
    entries = {key: CatalogEntry.model_validate(value) for key, value in raw["catalog"].items()}
    known = {ds.id for ds in registry}
    if unknown := entries.keys() - known:
        raise ValueError(f"unknown catalog IDs: {sorted(unknown)}")
    guides = set()
    for ds in registry:
        if ds.status is Status.AVAILABLE and ds.id not in entries:
            raise ValueError(f"{ds.id}: implemented datasets require catalog metadata")
    for key, entry in entries.items():
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
        if entry.guide in guides:
            raise ValueError(f"{key}: each dataset needs its own usage guide")
        guides.add(entry.guide)
    return entries


def dataset_path(ds: Dataset) -> Path:
    return Path("docs/generated/catalog") / ds.provider / f"{ds.name}.md"


def usage_link(ds: Dataset, entry: CatalogEntry) -> str:
    relative = posixpath.relpath(entry.guide, dataset_path(ds).parent.as_posix())
    return f"<!-- dataset-usage -->\n[Usage guide]({relative})."


def render_dataset(registry: Registry, ds: Dataset, entry: CatalogEntry) -> str:
    details = render_datasets_block(registry, [ds]).split(f"### {ds.id}\n", 1)[1]
    return (
        f"# {ds.title}\n\n{GENERATED_NOTE}\n\n"
        + usage_link(ds, entry)
        + "\n\n## Catalog reference\n"
        + details
    )


def render_all(registry: Registry) -> dict[Path, str]:
    """Generate only inside the owned catalog directory; never rewrite prose."""
    entries = catalog_entries(registry)
    outputs = {
        CATALOG_DIR / "index.md": "# Dataset catalog\n\n"
        + GENERATED_NOTE
        + "\n\n"
        + summary_table(registry, "../../providers/")
    }
    for info, datasets in by_provider(registry):
        outputs[CATALOG_DIR / f"{info.id}.md"] = (
            f"# {info.name} dataset catalog\n\n"
            f"[Provider access notes](../../providers/{info.id}.md). "
            "Status describes this source checkout; see version labels for release support.\n\n"
            + render_datasets_block(registry, datasets)
        )
        for ds in datasets:
            if ds.id in entries:
                outputs[ROOT / dataset_path(ds)] = render_dataset(registry, ds, entries[ds.id])
                # Preserve existing provider-page anchors while linking to the complete page.
                target = f"{ds.provider}/{ds.name}.md"
                heading = f"### {ds.id}\n"
                outputs[CATALOG_DIR / f"{info.id}.md"] = outputs[
                    CATALOG_DIR / f"{info.id}.md"
                ].replace(heading, heading + f"\n[Dataset and usage guide]({target}).\n")
    outputs[CATALOG_DIR / "versions.md"] = (
        "# Dataset versions and targets\n\n" + render_roadmap_block(registry)
    )
    return outputs


def sync(outputs: dict[Path, str], *, check: bool) -> list[Path]:
    if any(not path.is_relative_to(CATALOG_DIR) for path in outputs):
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
