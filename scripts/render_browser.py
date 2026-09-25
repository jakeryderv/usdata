"""Generate the website's metadata index from the same catalog as the docs."""

from __future__ import annotations

import json
import shlex
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from render_registry import (
    PACKAGE_VERSION,
    ROOT,
    availability,
    by_provider,
    check_usage_metadata,
    dataset_page_url,
    studies_of,
    walkthrough_of,
)

from usdata.manifest import TimeSelect
from usdata.models import Status, describe_duration
from usdata.registry import Registry

OUTPUT = ROOT / "web/public/datasets/catalog.json"
DOCS = "https://docs.usdata.dev/"


def docs_url(path: str) -> str:
    path = path.removeprefix("docs/")
    document = Path(path).with_suffix("")
    if document.name in {"README", "index"}:
        document = document.parent
    return DOCS + document.as_posix() + "/"


class _TextDates(yaml.SafeLoader):
    """YAML that keeps timestamps as the text a manifest wrote, for quoting back."""


_TextDates.yaml_implicit_resolvers = {
    first: [(tag, regex) for tag, regex in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _cli_value(value: Any) -> str:
    return ",".join(map(str, value)) if isinstance(value, list) else str(value)


def _python_value(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(map(_python_value, value)) + "]"
    if isinstance(value, bool | int | float):
        return repr(value)
    return json.dumps(str(value))


def _utc_text(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def quickstart(ds: Any, walkthrough: str | None) -> dict[str, str] | None:
    """The walkthrough's own query as a CLI line, a Python call, and a manifest.

    Nothing here is invented: the query is the first source of the manifest the
    walkthrough ran, so every quick start on the website has been executed. A
    source with ``select`` lists the window its rule implies and keeps one asset
    (ADR 0044). ``fetch`` has no such rule, so the CLI line fetches that window
    and says which file the manifest keeps, and the Python call keeps it with
    ``select_by_time``.
    """
    if walkthrough is None:
        return None
    manifest = ROOT / Path(walkthrough).parent / "dataset.yaml"
    if not manifest.is_file():
        return None
    text = manifest.read_text(encoding="utf-8")
    source = yaml.load(text, Loader=_TextDates)["sources"][0]
    rule = TimeSelect.model_validate(source["select"]) if "select" in source else None
    if rule is not None:
        start, end = map(_utc_text, rule.window())
        source = {**source, "start": start, "end": end}
    cli = [["usdata", "fetch", ds.id]]
    call = []
    for field, flag in (("location", "--location"), ("start", "--start"), ("end", "--end")):
        if field in source:
            cli.append([flag, str(source[field])])
            call.append(f"{field}={_python_value(source[field])}")
    if "bbox" in source:
        # A manifest writes the box as a mapping; the CLI and build_query take its four edges.
        box = source["bbox"]
        edges = [box[side] for side in ("west", "south", "east", "north")]
        cli.append(["--bbox", _cli_value(edges)])
        call.append(f"bbox=({', '.join(map(_python_value, edges))})")
    if source.get("variables"):
        cli.append(["--vars", _cli_value(source["variables"])])
        call.append(f"variables={_python_value(source['variables'])}")
    for key, value in (source.get("params") or {}).items():
        cli.append(["-p", f"{key}={_cli_value(value)}"])
        call.append(f"{key}={_python_value(value)}")
    line = " ".join(shlex.join(part) for part in cli)
    # A long command continues one option per line, as a person would paste it.
    command = line if len(line) <= 72 else " \\\n  ".join(shlex.join(part) for part in cli)
    arguments = "".join(f"        {argument},\n" for argument in call)
    fetched = f'items = fetch(\n    get("{ds.id}"),\n    build_query(\n{arguments}    ),\n)\n'
    item = "items[0]"
    if rule is None:
        imports = "from usdata import build_query, fetch, get\n\n"
    else:
        # fetch has no select rule (ADR 0044): list the window the rule implies,
        # then keep the one asset select_by_time chooses, as pull does.
        # The command leads, as on every quick start; the note on what it differs in follows.
        command += (
            "\n# fetch takes every file that starts in this window; the manifest keeps only\n"
            f"# the one starting {rule.direction.replace('_', ' ')} {_utc_text(rule.time)}."
        )
        imports = (
            "from datetime import datetime, timedelta\n\n"
            "from usdata import build_query, fetch, get, select_by_time\n\n"
        )
        fetched += (
            "chosen = select_by_time(\n"
            "    [item.asset for item in items],\n"
            f'    target=datetime.fromisoformat("{_utc_text(rule.time)}"),\n'
            f"    tolerance=timedelta(seconds={int(rule.within.total_seconds())}),\n"
            f'    direction="{rule.direction}",\n'
            ").asset\n"
        )
        item = "next(item for item in items if item.asset == chosen)"
    python = (
        imports + fetched + (f"data = {item}.open()\n" if ds.reader else f"print({item}.path)\n")
    )
    return {"cli": command, "python": python, "manifest": text}


def render() -> str:
    registry = Registry.bundled()
    check_usage_metadata(registry)
    datasets = []
    for provider, group in by_provider(registry):
        for dataset in group:
            implemented = dataset.status is Status.AVAILABLE
            walkthrough = walkthrough_of(dataset) if implemented else None
            datasets.append(
                {
                    "id": dataset.id,
                    "title": dataset.summary or dataset.title,
                    "product": dataset.title,
                    "description": dataset.description.strip(),
                    "provider": provider.name,
                    "provider_id": provider.id,
                    "domain": registry.domain(dataset.domain).name,
                    "system": (registry.system(dataset.system).name if dataset.system else None),
                    "availability": availability(dataset),
                    "since": dataset.since,
                    "keywords": dataset.keywords,
                    "formats": dataset.formats,
                    "selection": dataset.selection,
                    "inputs": dataset.inputs,
                    "credentials": (
                        dataset.credentials.model_dump() if dataset.credentials else None
                    ),
                    "reader_extra": dataset.reader,
                    "resolution": (dataset.resolution.model_dump() if dataset.resolution else None),
                    "update_frequency": dataset.update_frequency,
                    "latency": dataset.latency,
                    "citation": dataset.citation,
                    "terms": dataset.terms,
                    "homepage": dataset.homepage,
                    "variables": [v.model_dump() for v in dataset.variables],
                    "max_window": (
                        describe_duration(dataset.limits.max_window)
                        if dataset.limits and dataset.limits.max_window
                        else None
                    ),
                    "guide": docs_url(dataset.guide) if dataset.guide else None,
                    # A dataset's docs page is its guide, which ends in its reference.
                    "reference": (
                        docs_url(dataset.guide) + "#reference"
                        if implemented and dataset.guide
                        else DOCS + f"generated/catalog/{dataset.provider}/"
                    ),
                    "page": dataset_page_url(dataset) if implemented else None,
                    "walkthrough": walkthrough,
                    "studies": studies_of(dataset) if implemented else [],
                    "quickstart": quickstart(dataset, walkthrough),
                }
            )
    return json.dumps({"version": PACKAGE_VERSION, "datasets": datasets}, indent=2) + "\n"


if __name__ == "__main__":
    content = render()
    if "--check" in sys.argv:
        if not OUTPUT.is_file() or OUTPUT.read_text() != content:
            sys.exit("website catalog is stale: run 'just docs' and commit")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(content)
    print("website catalog is current")
