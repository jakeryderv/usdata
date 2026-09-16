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

from usdata.models import LATER, Dataset, ProviderInfo, Status, describe_duration
from usdata.providers import load_adapter
from usdata.registry import Registry, version_key

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
CATALOG_DIR = ROOT / "docs/generated/catalog"
STATUS_ORDER = [Status.AVAILABLE, Status.PLANNED]
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
        return (-counts[Status.AVAILABLE], registry.provider(pid).name)

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


def required(ds: Dataset, field: str) -> str:
    """Read a usage field that every implemented dataset must carry."""
    value = getattr(ds, field)
    if not isinstance(value, str):
        raise ValueError(f"{ds.id}: implemented datasets require {field}")
    return value


def dataset_table(datasets: list[Dataset]) -> str:
    lines = [
        "| Dataset | Availability | Files | What gets selected |",
        "|---|---|---|---|",
    ]
    for ds in datasets:
        anchor = _anchor(ds.id.replace(":", ""))
        summary = cell(required(ds, "summary"))
        formats = cell(", ".join(ds.formats))
        selection = cell(required(ds, "selection"))
        lines.append(
            f'| <span id="{anchor}"></span>[{summary}]({ds.provider}/{ds.name}.md) '
            f"| {availability(ds)} | {formats} | {selection} |"
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


def existing(ds: Dataset, path: str, label: str, root: Path) -> Path:
    """A repository-relative path the model already shaped, resolved in this checkout."""
    if not (root / path).is_file():
        raise ValueError(f"{ds.id}: {label} {path!r} does not exist in this checkout")
    return (root / path).resolve()


def check_usage_metadata(registry: Registry, root: Path = ROOT) -> None:
    """Every implemented dataset documents itself, with guide and example paths that exist.

    The model already validates the shape of each field; this adds what only a
    checkout can answer, plus the rule that every implemented dataset is documented.
    """
    guides: set[Path] = set()
    for ds in registry:
        if not all(re.fullmatch(r"[a-z0-9][a-z0-9-]*", part) for part in (ds.provider, ds.name)):
            raise ValueError(
                f"{ds.id}: catalog IDs must use lowercase letters, digits, and hyphens"
            )
        if ds.status is not Status.AVAILABLE:
            if ds.summary or ds.formats or ds.guide or ds.examples:
                raise ValueError(f"{ds.id}: usage metadata is only for implemented datasets")
            continue
        required(ds, "selection")
        required(ds, "inputs")
        if not ds.examples:
            raise ValueError(f"{ds.id}: implemented datasets require at least one example")
        for example in ds.examples:
            existing(ds, example, "example", root)
        guide = existing(ds, required(ds, "guide"), "guide", root)
        if guide in guides:
            raise ValueError(f"{ds.id}: each dataset needs its own usage guide")
        guides.add(guide)


def parameter_block(ds: Dataset) -> list[str]:
    """The adapter's declared ``--param`` keys, read from the class that implements them."""
    with load_adapter(ds) as adapter:
        declared = dict(adapter.accepted_params)
    if not declared:
        return ["This dataset accepts no provider-specific parameters."]
    return [
        "Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, "
        "or as keyword arguments to `build_query`.",
        "",
        "| Parameter | Meaning |",
        "|---|---|",
        *(f"| `{name}` | {cell(declared[name])} |" for name in sorted(declared)),
    ]


def description_block(ds: Dataset) -> list[str]:
    """Resolution, cadence, limits, terms, and citation, each line only when the entry states it."""
    resolution = ds.resolution
    window = ds.limits.max_window if ds.limits else None
    stated = [
        ("Spatial resolution", resolution.spatial if resolution else None),
        ("Temporal resolution", resolution.temporal if resolution else None),
        ("Updates", ds.update_frequency),
        ("Latency", ds.latency),
        ("Longest query window", describe_duration(window) if window else None),
        ("Terms of use", f"<{ds.terms}>" if ds.terms else None),
        ("Citation", ds.citation),
    ]
    return [f"- {label}: {value}" for label, value in stated if value]


def variable_block(ds: Dataset) -> list[str]:
    """The variables the entry declares, as the source names them."""
    if not ds.variables:
        return []
    return [
        "## Variables",
        "",
        "| Variable | Units | Meaning |",
        "|---|---|---|",
        *(
            f"| `{cell(v.name)}` | {cell(v.units) if v.units else '—'} "
            f"| {cell(v.description) if v.description else '—'} |"
            for v in ds.variables
        ),
        "",
    ]


def dataset_path(ds: Dataset) -> Path:
    return Path("docs/generated/catalog") / ds.provider / f"{ds.name}.md"


def usage_link(ds: Dataset) -> str:
    relative = posixpath.relpath(required(ds, "guide"), dataset_path(ds).parent.as_posix())
    return f"[Usage guide]({relative})."


def example_url(path: str) -> str:
    """Each maintained example folder has one canonical website page."""
    return f"https://usdata.dev/examples/{Path(path).parent.name}/"


def render_dataset(registry: Registry, ds: Dataset) -> str:
    examples = ", ".join(
        f"[{Path(path).parent.name.replace('-', ' ')}]({example_url(path)})" for path in ds.examples
    )
    reader = (
        f"`usdata[{ds.reader}]` · [Reader guide](../../../reference/readers.md)"
        if ds.reader
        else "Local files; no bundled reader for this format"
    )
    notice = (
        "Install from [source](../../../install.md#source-installation) to use this dataset."
        if availability(ds) == "Source only"
        else f"Included since usdata {ds.since}."
    )
    lines = [
        f"# {required(ds, 'summary')}",
        "",
        GENERATED_NOTE,
        "",
        f"`{ds.id}` · **{availability(ds)}** · {notice}",
        "",
        f"{ds.title}.",
        "",
        "## At a glance",
        "",
        f"- Files: {', '.join(ds.formats)}",
        f"- Selection: {required(ds, 'selection')}",
        f"- Required inputs: {required(ds, 'inputs')}",
        f"- Open locally: {reader}",
        f"- Examples: {examples}",
        "",
        "## Parameters",
        "",
        *parameter_block(ds),
        "",
        *variable_block(ds),
        "## Usage and limitations",
        "",
        usage_link(ds),
        "",
        "## Catalog reference",
        "",
        f"- Availability: {implementation_version(ds)}",
        f"- Domain: {registry.domain(ds.domain).name}",
        *description_block(ds),
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
    check_usage_metadata(registry)
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
        + dataset_table(implemented)
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
            + (dataset_table(available) if available else "None implemented yet.\n")
            + "\n## Planned datasets\n\n"
            + planned_block(registry, planned)
        )
        for ds in available:
            outputs[ROOT / dataset_path(ds)] = render_dataset(registry, ds)
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
