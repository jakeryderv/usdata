"""Render the bundled dataset registry to docs/reference/datasets.md.

Run via ``just docs``. CI fails if the rendered file is out of date.
"""

from __future__ import annotations

from pathlib import Path

from usdata.models import Dataset
from usdata.registry import Registry

OUT = Path(__file__).resolve().parents[1] / "docs/reference/datasets.md"


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


def render(registry: Registry) -> str:
    datasets = sorted(registry, key=lambda d: d.id)
    lines = [
        "# Datasets",
        "",
        "Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.",
        "",
        "| Id | Title | Provider | Protocol | Server-side subsetting |",
        "|---|---|---|---|---|",
    ]
    for ds in datasets:
        lines.append(
            f"| [`{ds.id}`](#{ds.id.replace(':', '')}) | {ds.title} | {ds.provider} "
            f"| {ds.protocol.value} | {_caps(ds)} |"
        )
    for ds in datasets:
        lines += [
            "",
            f"## {ds.id}",
            "",
            f"**{ds.title}**",
            "",
            ds.description.strip(),
            "",
            f"- Homepage: {ds.homepage or 'not stated'}",
            f"- License: {ds.license or 'not stated'}",
            f"- Extent: {_extent(ds)}",
            f"- Keywords: {', '.join(ds.keywords) or 'none'}",
            f"- Adapter: `{ds.adapter}`",
        ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(Registry.bundled()))
    print(f"wrote {OUT}")
