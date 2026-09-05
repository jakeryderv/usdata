"""Render the dataset registry to docs/reference/datasets.md and the README summary.

Run via ``just docs``. ``--check`` renders without writing and exits 1 if either
file on disk differs, which is what ``just check`` and CI run.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

from usdata.models import Dataset, Status
from usdata.registry import Registry

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "docs/reference/datasets.md"
README = ROOT / "README.md"
MARK_START, MARK_END = "<!-- registry:start -->", "<!-- registry:end -->"
STATUS_ORDER = [Status.AVAILABLE, Status.STUB, Status.PLANNED]
STATUS_LABEL = {Status.AVAILABLE: "available", Status.STUB: "stub", Status.PLANNED: "planned"}


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


def _by_provider(registry: Registry) -> list[tuple[str, list[Dataset]]]:
    groups: dict[str, list[Dataset]] = {}
    for ds in registry:
        groups.setdefault(ds.provider, []).append(ds)

    def progress(pid: str) -> tuple[int, int, str]:
        counts = Counter(d.status for d in groups[pid])
        return (-counts[Status.AVAILABLE], -counts[Status.STUB], registry.provider(pid).name)

    ordered = sorted(groups, key=progress)
    return [
        (pid, sorted(groups[pid], key=lambda d: (STATUS_ORDER.index(d.status), d.id)))
        for pid in ordered
    ]


def render_reference(registry: Registry) -> str:
    """Full reference: one table per provider, then a section per dataset."""
    lines = [
        "# Datasets",
        "",
        "Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.",
        "",
        "Status: **available** has a tested adapter, **stub** has an adapter class that is "
        "not implemented yet, **planned** is a registry entry only.",
    ]
    for pid, datasets in _by_provider(registry):
        info = registry.provider(pid)
        title = f"[{info.name}]({info.homepage})" if info.homepage else info.name
        lines += [
            "",
            f"## {info.name}",
            "",
            f"Provider id `{pid}`. {title}.",
            "",
            "| Dataset | Status | Description | Protocol | Server-side subsetting |",
            "|---|---|---|---|---|",
        ]
        for ds in datasets:
            first_sentence = ds.description.strip().split(". ")[0].rstrip(".") + "."
            lines.append(
                f"| [`{ds.id}`](#{_anchor(ds.id.replace(':', ''))}) | {STATUS_LABEL[ds.status]} "
                f"| {first_sentence} | {ds.protocol.value} | {_caps(ds)} |"
            )
    lines += ["", "---", "", "# Dataset details"]
    for _, datasets in _by_provider(registry):
        for ds in datasets:
            lines += [
                "",
                f"## {ds.id}",
                "",
                f"**{ds.title}** · {STATUS_LABEL[ds.status]}",
                "",
                ds.description.strip(),
                "",
                f"- Homepage: {ds.homepage or 'not stated'}",
                f"- License: {ds.license or 'not stated'}",
                f"- Extent: {_extent(ds)}",
                f"- Keywords: {', '.join(ds.keywords) or 'none'}",
                f"- Adapter: `{ds.adapter}`" if ds.adapter else "- Adapter: none yet",
            ]
    return "\n".join(lines) + "\n"


def render_summary(registry: Registry) -> str:
    """Compact per-provider table for the README."""
    lines = [
        "| Provider | Available | Stub | Planned | Datasets |",
        "|---|---:|---:|---:|---|",
    ]
    for pid, datasets in _by_provider(registry):
        info = registry.provider(pid)
        counts = Counter(d.status for d in datasets)
        names = ", ".join(
            f"`{d.name}`" if d.status is Status.AVAILABLE else f"_{d.name}_" for d in datasets
        )
        lines.append(
            f"| [{info.name}](docs/reference/datasets.md#{_anchor(info.name)}) "
            f"| {counts[Status.AVAILABLE]} | {counts[Status.STUB]} | {counts[Status.PLANNED]} "
            f"| {names} |"
        )
    lines += [
        "",
        "Available datasets are in `code`; stubs and planned ones in _italics_. "
        "Full details in [docs/reference/datasets.md](docs/reference/datasets.md).",
    ]
    return "\n".join(lines) + "\n"


def splice(text: str, block: str) -> str:
    """Replace the content between the README markers with ``block``."""
    start, end = text.index(MARK_START) + len(MARK_START), text.index(MARK_END)
    return text[:start] + "\n" + block + text[end:]


if __name__ == "__main__":
    registry = Registry.bundled()
    outputs = {
        REFERENCE: render_reference(registry),
        README: splice(README.read_text(), render_summary(registry)),
    }
    if "--check" in sys.argv:
        stale = [p for p, text in outputs.items() if not p.exists() or p.read_text() != text]
        if stale:
            names = ", ".join(p.relative_to(ROOT).as_posix() for p in stale)
            sys.exit(f"generated docs are stale ({names}): run 'just docs' and commit")
        print("generated docs are current")
    else:
        REFERENCE.parent.mkdir(parents=True, exist_ok=True)
        for p, text in outputs.items():
            p.write_text(text)
        print(f"wrote {REFERENCE.relative_to(ROOT)} and README summary")
