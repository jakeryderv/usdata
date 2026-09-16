"""Generate the website's metadata index from the same catalog as the docs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from render_registry import (
    PACKAGE_VERSION,
    ROOT,
    availability,
    by_provider,
    check_usage_metadata,
    example_url,
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


def render() -> str:
    registry = Registry.bundled()
    check_usage_metadata(registry)
    datasets = []
    for provider, group in by_provider(registry):
        for dataset in group:
            implemented = dataset.status is Status.AVAILABLE
            datasets.append(
                {
                    "id": dataset.id,
                    "title": dataset.summary or dataset.title,
                    "description": dataset.description.strip(),
                    "provider": provider.name,
                    "domain": registry.domain(dataset.domain).name,
                    "system": (registry.system(dataset.system).name if dataset.system else None),
                    "availability": availability(dataset),
                    "since": dataset.since,
                    "keywords": dataset.keywords,
                    "formats": dataset.formats,
                    "selection": dataset.selection,
                    "inputs": dataset.inputs,
                    "reader_extra": dataset.reader,
                    "resolution": (dataset.resolution.model_dump() if dataset.resolution else None),
                    "update_frequency": dataset.update_frequency,
                    "latency": dataset.latency,
                    "citation": dataset.citation,
                    "terms": dataset.terms,
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
                    "examples": [
                        {
                            "title": Path(path).parent.name.replace("-", " ").capitalize(),
                            "url": example_url(path),
                        }
                        for path in dataset.examples
                    ],
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
