"""Render the dataset registry into the docs.

Outputs live exclusively under docs/generated/catalog/.
Provider access notes, usage guides, indexes, and the roadmap are handwritten.

Run via ``just docs``. ``--check`` renders without writing and exits 1 if any
generated content on disk differs, which is what ``just check`` and CI run.
"""

from __future__ import annotations

import json
import posixpath
import re
import sys
import tomllib
from collections import Counter
from pathlib import Path, PurePosixPath

import yaml

from usdata.models import LATER, Dataset, ProviderInfo, Status, describe_duration
from usdata.providers import adapter_class
from usdata.registry import Registry, version_key

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
CATALOG_DIR = ROOT / "docs/generated/catalog"
STATUS_ORDER = [Status.AVAILABLE, Status.PLANNED]
# An HTML comment: kept in the source for editors and for sync(), never shown to readers.
GENERATED_NOTE = (
    "<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->"
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
        page = posixpath.relpath(required(ds, "guide"), CATALOG_DIR.relative_to(ROOT).as_posix())
        lines.append(
            f'| <span id="{anchor}"></span>[{summary}]({page}) '
            f"| {availability(ds)} | {formats} | {selection} |"
        )
    return "\n".join(lines) + "\n"


def system_sections(registry: Registry, datasets: list[Dataset]) -> str:
    """Datasets grouped by the system they come from, ungrouped ones under the provider."""
    groups: dict[str | None, list[Dataset]] = {}
    for ds in datasets:
        groups.setdefault(ds.system, []).append(ds)
    blocks = [dataset_table(groups[None])] if None in groups else []
    for system_id, group in groups.items():
        if system_id is None:
            continue
        info = registry.system(system_id)
        heading = f"[{info.name}]({info.homepage})" if info.homepage else info.name
        blocks.append(f"### {heading}\n\n" + dataset_table(group))
    return "\n".join(blocks)


def _credentials_text(ds: Dataset) -> str:
    """The variables a dataset reads its key from, and where the agency issues one."""
    assert ds.credentials is not None
    names = ", ".join(f"`{name}`" for name in ds.credentials.variables)
    return f"{names} in the environment ([request a key]({ds.credentials.signup}))"


def _credentials_line(ds: Dataset) -> list[str]:
    """The at-a-glance line for a dataset that needs credentials, or nothing."""
    return [f"- Credentials: {_credentials_text(ds)}"] if ds.credentials else []


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
            *([f"Credentials: {_credentials_text(ds)}."] if ds.credentials else []),
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
    check_example_relationships(registry, root)


_ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
README_COUNTS = re.compile(r"(\S+) datasets are available today and (\S+) more are planned")


def spelled(number: int) -> str:
    """A count below one hundred as the README writes it: ``twenty-three``."""
    if not 0 <= number < 100:
        raise ValueError(f"cannot spell {number}; reword the README sentence and this check")
    if number < 20:
        return _ONES[number]
    tens, ones = divmod(number, 10)
    return _TENS[tens - 2] + (f"-{_ONES[ones]}" if ones else "")


def check_readme_counts(registry: Registry, root: Path = ROOT) -> None:
    """The README's available and planned counts are the registry's.

    The README is handwritten and stays that way; this only refuses a sentence
    the registry has outgrown, naming the words it should now hold.
    """
    available = sum(ds.status is Status.AVAILABLE for ds in registry)
    expected = (spelled(available), spelled(len(registry) - available))
    found = README_COUNTS.search((root / "README.md").read_text())
    if found is None:
        raise ValueError("README.md no longer states how many datasets are available and planned")
    if (found[1].lower(), found[2].lower()) != expected:
        raise ValueError(
            f"README.md says {found[1]} datasets are available and {found[2]} planned; "
            f"the registry has {expected[0]} and {expected[1]}"
        )


def parameter_block(ds: Dataset) -> list[str]:
    """The adapter's declared ``--param`` keys, read from the class that implements them."""
    declared = dict(adapter_class(ds).accepted_params)
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
        "### Variables",
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


def snippet_line(ds: Dataset) -> str:
    """The line a dataset's guide ends with, which appends its generated reference."""
    return f'--8<-- "{dataset_path(ds).relative_to("docs").as_posix()}"'


def guide_url_path(ds: Dataset) -> str:
    """The docs URL path of the dataset's one page, its guide."""
    return (
        "/"
        + PurePosixPath(required(ds, "guide")).relative_to("docs").with_suffix("").as_posix()
        + "/"
    )


WEBSITE = "https://usdata.dev/"
EXAMPLE_KINDS = ("datasets", "studies")


def example_folder(path: str) -> tuple[str, str]:
    """The kind (``datasets`` or ``studies``) and folder name of an example file (ADR 0041)."""
    parts = PurePosixPath(path).parts
    if len(parts) != 4 or parts[0] != "examples" or parts[1] not in EXAMPLE_KINDS:
        raise ValueError(f"{path}: examples live in examples/datasets/ or examples/studies/")
    return parts[1], parts[2]


def walkthrough_folder(ds: Dataset) -> str:
    """The one folder a dataset's walkthrough can live in."""
    return f"{ds.provider}-{ds.name}"


def dataset_page_url(ds: Dataset) -> str:
    """The website page for an implemented dataset."""
    return f"{WEBSITE}datasets/{ds.provider}/{ds.name}/"


def example_url(path: str) -> str:
    """Each maintained example folder has one canonical website page."""
    kind, folder = example_folder(path)
    if kind == "studies":
        return f"{WEBSITE}studies/{folder}/"
    provider, _, name = folder.partition("-")
    return f"{WEBSITE}datasets/{provider}/{name}/"


def load_catalog(root: Path = ROOT) -> dict[str, list]:
    return json.loads((root / "examples/catalog.json").read_text(encoding="utf-8"))


def study_title(slug: str, root: Path = ROOT) -> str:
    """The question a study's catalog entry asks."""
    for entry in load_catalog(root)["studies"]:
        if entry["slug"] == slug:
            return entry["title"]
    raise ValueError(f"study {slug!r} is not in examples/catalog.json")


def walkthrough_of(ds: Dataset) -> str | None:
    """The dataset's walkthrough file, which the registry lists first, if it has one."""
    first = ds.examples[0] if ds.examples else None
    return first if first and example_folder(first)[0] == "datasets" else None


def studies_of(ds: Dataset) -> list[str]:
    """The study folders whose manifests use this dataset, in registry order."""
    return [example_folder(path)[1] for path in ds.examples if example_folder(path)[0] == "studies"]


def check_example_relationships(registry: Registry, root: Path = ROOT) -> None:
    """The registry, the example folders, and each study's manifest agree (ADR 0041).

    A dataset lists only its own walkthrough, first, and must list it once the
    folder exists; it lists every study whose manifest names it and no other.
    """
    catalog = load_catalog(root)
    studies = [entry["slug"] for entry in catalog["studies"]]
    folders = {
        kind: sorted(p.name for p in (root / "examples" / kind).iterdir() if p.is_dir())
        for kind in EXAMPLE_KINDS
    }
    if sorted(studies) != folders["studies"] or len(set(studies)) != len(studies):
        raise ValueError("examples/catalog.json must list every study folder exactly once")
    for folder in catalog["pinned"]:
        if not (root / "examples" / folder / "dataset.yaml").is_file():
            raise ValueError(f"pinned example {folder!r} has no dataset.yaml")
    listed: dict[str, set[str]] = {slug: set() for slug in studies}
    implemented = {walkthrough_folder(ds): ds for ds in registry if ds.status is Status.AVAILABLE}
    for folder in folders["datasets"]:
        if folder not in implemented:
            raise ValueError(f"examples/datasets/{folder}: no implemented dataset has this folder")
    for ds in implemented.values():
        kinds = [example_folder(path) for path in ds.examples]
        own = walkthrough_folder(ds)
        walkthroughs = [folder for kind, folder in kinds if kind == "datasets"]
        if walkthroughs and (walkthroughs != [own] or kinds[0] != ("datasets", own)):
            raise ValueError(
                f"{ds.id}: list only its own walkthrough, examples/datasets/{own}/, first"
            )
        if not walkthroughs:
            raise ValueError(
                f"{ds.id}: every implemented dataset needs its walkthrough, "
                f"examples/datasets/{own}/{own}.ipynb, listed first"
            )
        for path in ds.examples:
            kind, folder = example_folder(path)
            if PurePosixPath(path).name != f"{folder}.ipynb":
                raise ValueError(
                    f"{ds.id}: list the notebook, examples/{kind}/{folder}/{folder}.ipynb"
                )
        for kind, folder in kinds:
            if kind == "studies":
                if folder not in listed:
                    raise ValueError(f"{ds.id}: study {folder!r} is not in examples/catalog.json")
                listed[folder].add(ds.id)
    for slug in studies:
        manifest = yaml.safe_load((root / "examples/studies" / slug / "dataset.yaml").read_text())
        used = {source["dataset"] for source in manifest["sources"]}
        if used != listed[slug]:
            raise ValueError(
                f"study {slug}: its manifest uses {sorted(used)} but the registry links "
                f"{sorted(listed[slug])}; list the study under exactly the datasets it uses"
            )


def render_dataset(registry: Registry, ds: Dataset) -> str:
    """The generated reference a dataset's guide includes at its end (ADR 0041).

    The guide in ``docs/providers/`` is the dataset's one docs page; this file is
    never a page of its own, so its links are relative to ``docs/providers/``.
    """
    studies = "; ".join(
        f"[{study_title(slug)}]({WEBSITE}studies/{slug}/)" for slug in studies_of(ds)
    )
    reader = (
        f"`usdata[{ds.reader}]` · [Reader guide](../reference/readers.md)"
        if ds.reader
        else "Local files; no bundled reader for this format"
    )
    notice = (
        "Install from [source](../install.md#source-installation) to use this dataset."
        if availability(ds) == "Source only"
        else f"Included since usdata {ds.since}."
    )
    lines = [
        GENERATED_NOTE,
        "",
        "## Reference",
        "",
        f"`{ds.id}` · **{availability(ds)}** · {notice} {ds.title}.",
        "",
        "### At a glance",
        "",
        f"- Files: {', '.join(ds.formats)}",
        f"- Selection: {required(ds, 'selection')}",
        f"- Required inputs: {required(ds, 'inputs')}",
        *_credentials_line(ds),
        f"- Open locally: {reader}",
        f"- On usdata.dev: [{required(ds, 'summary')}]({dataset_page_url(ds)})"
        + (", with a walkthrough" if walkthrough_of(ds) else ""),
        *([f"- Studies: {studies}"] if studies else []),
        "",
        "### Parameters",
        "",
        *parameter_block(ds),
        "",
        *variable_block(ds),
        "### Catalog facts",
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
    ]
    return "\n".join(lines)


DOCS_REDIRECTS = ROOT / "docs/_redirects"


def render_redirects(implemented: list[Dataset]) -> str:
    """Cloudflare rules sending each retired generated dataset page to its guide."""
    lines = [
        "# Generated by `just docs` from src/usdata/data/registry.yaml. Do not edit by hand.",
    ]
    for ds in implemented:
        old = f"/generated/catalog/{ds.provider}/{ds.name}"
        lines += [f"{old}/ {guide_url_path(ds)} 301", f"{old} {guide_url_path(ds)} 301"]
    return "\n".join(lines) + "\n"


def check_guides_include_reference(registry: Registry, root: Path = ROOT) -> None:
    """Each implemented dataset's guide ends by including its generated reference."""
    for ds in registry:
        if ds.status is not Status.AVAILABLE:
            continue
        guide = (root / required(ds, "guide")).read_text().rstrip("\n")
        if not guide.endswith(snippet_line(ds)):
            raise ValueError(f"{ds.guide}: end the guide with the line {snippet_line(ds)}")


AVAILABILITY_NOTE = (
    f"**Released** is included in usdata {PACKAGE_VERSION}. **Source only** is implemented "
    "in this checkout and requires a source installation. **Planned** cannot fetch data yet."
    "\n"
)


def render_all(registry: Registry) -> dict[Path, str]:
    """Generate only inside the owned catalog directory; never rewrite prose."""
    check_usage_metadata(registry)
    check_readme_counts(registry)
    implemented = [
        ds
        for _, datasets in by_provider(registry)
        for ds in datasets
        if ds.status is Status.AVAILABLE
    ]
    check_guides_include_reference(registry)
    outputs = {
        CATALOG_DIR / "index.md": "# Dataset reference\n\n"
        + GENERATED_NOTE
        + "\n\n"
        + "Each dataset has one page here: how to select it, what arrives, what the service "
        "does not say, and its generated reference. To browse datasets with previews and "
        "walkthroughs, use the [dataset grid on usdata.dev](https://usdata.dev/datasets/).\n\n"
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
            + (system_sections(registry, available) if available else "None implemented yet.\n")
            + "\n## Planned datasets\n\n"
            + planned_block(registry, planned)
        )
        for ds in available:
            outputs[ROOT / dataset_path(ds)] = render_dataset(registry, ds)
    outputs[DOCS_REDIRECTS] = render_redirects(implemented)
    outputs[CATALOG_DIR / "versions.md"] = (
        "# Dataset versions and targets\n\n" + render_roadmap_block(registry)
    )
    return outputs


def sync(outputs: dict[Path, str], *, check: bool) -> list[Path]:
    if any(
        not path.resolve().is_relative_to(CATALOG_DIR.resolve()) and path != DOCS_REDIRECTS
        for path in outputs
    ):
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
