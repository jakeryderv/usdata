"""Generate the website's metadata index from the same catalog as the docs."""

from __future__ import annotations

import json
import shlex
import sys
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


def quickstart(ds: Any, walkthrough: str | None) -> dict[str, str] | None:
    """The walkthrough's own query as a CLI line, a Python call, and a manifest.

    Nothing here is invented: the query is the first source of the manifest the
    walkthrough ran, so every quick start on the website has been executed.
    """
    if walkthrough is None:
        return None
    manifest = ROOT / Path(walkthrough).parent / "dataset.yaml"
    if not manifest.is_file():
        return None
    text = manifest.read_text(encoding="utf-8")
    source = yaml.load(text, Loader=_TextDates)["sources"][0]
    cli = [["usdata", "fetch", ds.id]]
    call = []
    for field, flag in (("location", "--location"), ("start", "--start"), ("end", "--end")):
        if field in source:
            cli.append([flag, str(source[field])])
            call.append(f"{field}={_python_value(source[field])}")
    if "bbox" in source:
        cli.append(["--bbox", _cli_value(source["bbox"])])
        call.append(f"bbox={_python_value(source['bbox'])}")
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
    python = (
        "from usdata import build_query, fetch, get\n\n"
        f'items = fetch(\n    get("{ds.id}"),\n    build_query(\n{arguments}    ),\n)\n'
        + ("data = items[0].open()\n" if ds.reader else "print(items[0].path)\n")
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
                    "reference": (
                        DOCS + f"generated/catalog/{dataset.provider}/{dataset.name}/"
                        if implemented
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
