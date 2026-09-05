"""Render the dataset registry into the docs.

Outputs:

- ``docs/providers/README.md``: generated index, one row per provider.
- ``docs/providers/<provider>.md``: hand-written notes with a generated block
  between ``<!-- datasets:start -->`` and ``<!-- datasets:end -->``. Missing
  files are created from a template.
- ``README.md``: the same provider summary between ``<!-- registry:start -->``
  and ``<!-- registry:end -->``.

Run via ``just docs``. ``--check`` renders without writing and exits 1 if any
generated content on disk differs, which is what ``just check`` and CI run.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

from usdata.models import Dataset, ProviderInfo, Status
from usdata.registry import Registry

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
PROVIDERS_DIR = ROOT / "docs/providers"
INDEX = PROVIDERS_DIR / "README.md"
README_MARKS = ("<!-- registry:start -->", "<!-- registry:end -->")
PAGE_MARKS = ("<!-- datasets:start -->", "<!-- datasets:end -->")
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

    return [
        (
            registry.provider(pid),
            sorted(groups[pid], key=lambda d: (STATUS_ORDER.index(d.status), d.id)),
        )
        for pid in sorted(groups, key=progress)
    ]


def summary_table(registry: Registry, link_prefix: str) -> str:
    """Per-provider counts; ``link_prefix`` is the relative path to docs/providers/."""
    lines = [
        "| Provider | Available | Stub | Planned | Datasets |",
        "|---|---:|---:|---:|---|",
    ]
    for info, datasets in by_provider(registry):
        counts = Counter(d.status for d in datasets)
        names = ", ".join(
            f"`{d.name}`" if d.status is Status.AVAILABLE else f"_{d.name}_" for d in datasets
        )
        lines.append(
            f"| [{info.name}]({link_prefix}{info.id}.md) "
            f"| {counts[Status.AVAILABLE]} | {counts[Status.STUB]} | {counts[Status.PLANNED]} "
            f"| {names} |"
        )
    return "\n".join(lines) + "\n"


def render_readme_block(registry: Registry) -> str:
    """Block for the top-level README."""
    return (
        summary_table(registry, "docs/providers/")
        + "\nAvailable datasets are in `code`; stubs and planned ones in _italics_. "
        "Each provider page has access notes and full dataset details.\n"
    )


def render_index(registry: Registry) -> str:
    """docs/providers/README.md, fully generated."""
    return (
        "# Providers\n\n"
        + GENERATED_NOTE
        + "\n\nStatus: **available** has a tested adapter, **stub** has an adapter class "
        "that is not implemented yet, **planned** is a registry entry only.\n\n"
        + summary_table(registry, "")
    )


def render_datasets_block(info: ProviderInfo, datasets: list[Dataset]) -> str:
    """Generated block for one provider page: table, then details."""
    lines = [
        GENERATED_NOTE,
        "",
        "| Dataset | Status | Description | Protocol | Server-side subsetting |",
        "|---|---|---|---|---|",
    ]
    for ds in datasets:
        lines.append(
            f"| [`{ds.id}`](#{_anchor(ds.id.replace(':', ''))}) | {ds.status.value} "
            f"| {_first_sentence(ds.description)} | {ds.protocol.value} | {_caps(ds)} |"
        )
    for ds in datasets:
        lines += [
            "",
            f"### {ds.id}",
            "",
            f"**{ds.title}** · {ds.status.value}",
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


def page_template(info: ProviderInfo) -> str:
    """Starting content for a provider page that does not exist yet."""
    home = f"Homepage: {info.homepage}\n\n" if info.homepage else ""
    return (
        f"# {info.name}\n\n"
        f"Provider id `{info.id}`. {home}"
        "## Access notes\n\n"
        "No notes yet. Add how this agency publishes data, authentication requirements, "
        "quirks, and links to its own documentation as adapters get built.\n\n"
        "## Datasets\n\n"
        f"{PAGE_MARKS[0]}\n{PAGE_MARKS[1]}\n"
    )


def splice(text: str, marks: tuple[str, str], block: str) -> str:
    """Replace the content between two marker comments with ``block``."""
    start, end = text.index(marks[0]) + len(marks[0]), text.index(marks[1])
    return text[:start] + "\n" + block + text[end:]


def render_all(registry: Registry) -> dict[Path, str]:
    """Every file this script owns (or owns a block of), with its full intended content."""
    outputs = {
        README: splice(README.read_text(), README_MARKS, render_readme_block(registry)),
        INDEX: render_index(registry),
    }
    for info, datasets in by_provider(registry):
        page = PROVIDERS_DIR / f"{info.id}.md"
        current = page.read_text() if page.exists() else page_template(info)
        outputs[page] = splice(current, PAGE_MARKS, render_datasets_block(info, datasets))
    return outputs


if __name__ == "__main__":
    outputs = render_all(Registry.bundled())
    if "--check" in sys.argv:
        stale = [p for p, text in outputs.items() if not p.exists() or p.read_text() != text]
        if stale:
            names = ", ".join(p.relative_to(ROOT).as_posix() for p in stale)
            sys.exit(f"generated docs are stale ({names}): run 'just docs' and commit")
        print("generated docs are current")
    else:
        PROVIDERS_DIR.mkdir(parents=True, exist_ok=True)
        for p, text in outputs.items():
            p.write_text(text)
        print(f"wrote {len(outputs)} files under docs/providers and the README summary")
