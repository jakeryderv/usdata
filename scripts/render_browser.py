"""Generate the website's metadata index from the same catalog as the docs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from render_registry import PACKAGE_VERSION, ROOT, availability, by_provider, catalog_entries

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
    entries = catalog_entries(registry)
    datasets = []
    for provider, group in by_provider(registry):
        for dataset in group:
            entry = entries.get(dataset.id)
            datasets.append(
                {
                    "id": dataset.id,
                    "title": entry.summary if entry else dataset.title,
                    "description": dataset.description.strip(),
                    "provider": provider.name,
                    "domain": registry.domain(dataset.domain).name,
                    "availability": availability(dataset),
                    "since": dataset.since,
                    "keywords": dataset.keywords,
                    "formats": entry.formats if entry else [],
                    "selection": entry.selection if entry else None,
                    "inputs": entry.inputs if entry else None,
                    "reader_extra": entry.reader_extra if entry else None,
                    "guide": docs_url(entry.guide) if entry else None,
                    "reference": (
                        DOCS + f"generated/catalog/{dataset.provider}/{dataset.name}/"
                        if entry
                        else DOCS + f"generated/catalog/{dataset.provider}/"
                    ),
                    "examples": [
                        {
                            "title": Path(path).parent.name.replace("-", " ").capitalize(),
                            "url": docs_url(path),
                        }
                        for path in entry.examples
                    ]
                    if entry
                    else [],
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
