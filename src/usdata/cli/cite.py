"""The ``cite`` command: citations for a dataset or for a manifest's pinned inputs."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from usdata.cite import Citation, cite_dataset, cite_lockfile, render_bibtex, render_text
from usdata.manifest import lockfile_path
from usdata.pull import ManifestChanged
from usdata.registry import DatasetNotFound, default_registry

MANIFEST_SUFFIXES = (".yaml", ".yml")
"""Suffixes that make an argument a manifest path rather than a dataset id."""


class CitationFormat(StrEnum):
    """How ``--format`` renders the citations."""

    TEXT = "text"
    BIBTEX = "bibtex"


def cite(
    target: Annotated[
        str, typer.Argument(help="Dataset id, e.g. noaa:ghcn-daily, or a manifest path.")
    ],
    format: Annotated[
        CitationFormat, typer.Option(help="Rendering of the citations.")
    ] = CitationFormat.TEXT,
    as_json: Annotated[
        bool, typer.Option("--json", help="Emit a JSON array of citation records and nothing else.")
    ] = False,
) -> None:
    """Print how to cite a dataset, or the inputs a manifest's lockfile pins."""
    path = Path(target)
    citations = (
        _manifest_citations(path)
        if path.suffix in MANIFEST_SUFFIXES or path.is_file()
        else [_dataset_citation(target)]
    )
    if as_json:
        typer.echo(json.dumps([c.model_dump(mode="json") for c in citations], indent=2))
    elif format is CitationFormat.BIBTEX:
        typer.echo(render_bibtex(citations))
    else:
        typer.echo(render_text(citations))


def _dataset_citation(dataset_id: str) -> Citation:
    """The registry entry's citation, or exit 2 when no entry has that id."""
    try:
        return cite_dataset(default_registry().get(dataset_id))
    except DatasetNotFound:
        typer.secho(f"Unknown dataset: {dataset_id}", err=True, fg="red")
        raise typer.Exit(code=2) from None


def _manifest_citations(manifest: Path) -> list[Citation]:
    """The lockfile's citations, or exit 2 when it is absent, stale, or unreadable."""
    if not manifest.is_file():
        typer.secho(f"no manifest at {manifest}", err=True, fg="red")
        raise typer.Exit(code=2)
    lock = lockfile_path(manifest)
    if not lock.exists():
        typer.secho(f"no lockfile at {lock}; run pull first", err=True, fg="red")
        raise typer.Exit(code=2)
    try:
        return cite_lockfile(manifest)
    except (DatasetNotFound, ManifestChanged, ValueError, OSError) as e:
        typer.secho(str(e), err=True, fg="red")
        raise typer.Exit(code=2) from None
