"""The ``cache`` commands: where the cache is, what it holds, and what to drop."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated

import typer

from usdata.cache import cache_dir
from usdata.cache_ops import (
    CacheEntry,
    candidates,
    entries,
    parse_duration,
    pinned_paths,
    prune,
    total_size,
)

cache_app = typer.Typer(
    name="cache",
    help="Inspect and prune the local file cache.",
    no_args_is_help=True,
)

_UNITS = (("GiB", 1024**3), ("MiB", 1024**2), ("KiB", 1024))

_DatasetOption = Annotated[
    str | None, typer.Option(help="Restrict to one dataset id, e.g. noaa:ghcn-daily.")
]


def _human(size: int) -> str:
    """Bytes in the largest binary unit that leaves a number above one."""
    for label, unit in _UNITS:
        if size >= unit:
            return f"{size / unit:.1f} {label}"
    return f"{size} B"


@cache_app.command()
def path() -> None:
    """Print the cache directory, whether or not it exists yet."""
    typer.echo(str(cache_dir()))


@cache_app.command("list")
def list_files(
    dataset: _DatasetOption = None,
    as_json: Annotated[
        bool, typer.Option("--json", help="Emit a JSON array of cache records and nothing else.")
    ] = False,
) -> None:
    """List cached files with their size and when they were retrieved."""
    found = [entry for entry in entries() if dataset is None or entry.dataset_id == dataset]
    if as_json:
        typer.echo(json.dumps([entry.model_dump(mode="json") for entry in found], indent=2))
    elif found:
        _echo_entries(found)
    else:
        typer.echo("No cached files." if dataset is None else f"No cached files for {dataset}.")
    if not found:
        raise typer.Exit(code=1)


@cache_app.command()
def size() -> None:
    """Print how much room the cached data files take."""
    total = total_size()
    typer.echo(f"{_human(total)}\t{total} bytes\t{cache_dir()}")


@cache_app.command("prune")
def prune_files(
    older_than: Annotated[
        str | None,
        typer.Option("--older-than", help="Remove files at least this old: 30d, 12h, or P30D."),
    ] = None,
    dataset: _DatasetOption = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="List what would be removed and remove nothing.")
    ] = False,
    include_pinned: Annotated[
        bool,
        typer.Option("--include-pinned", help="Also remove files a lockfile here pins."),
    ] = False,
) -> None:
    """Remove cached files by age or dataset, keeping what a lockfile here pins."""
    if older_than is None and dataset is None:
        typer.secho("prune needs --older-than, --dataset, or both", err=True, fg="red")
        raise typer.Exit(code=2)
    try:
        age = parse_duration(older_than) if older_than is not None else None
        pinned = frozenset() if include_pinned else frozenset(pinned_paths())
        now = datetime.now(UTC)
        kept = [
            entry
            for entry in candidates(older_than=age, dataset=dataset, now=now)
            if entry.path in pinned
        ]
        removed = prune(older_than=age, dataset=dataset, pinned=pinned, dry_run=dry_run, now=now)
    except (OSError, ValueError) as e:
        typer.secho(str(e), err=True, fg="red")
        raise typer.Exit(code=2) from None
    for entry in removed:
        typer.echo(f"{entry.path}\t{entry.size} bytes")
    verb = "would remove" if dry_run else "removed"
    summary = f"{verb} {len(removed)} file(s), {_human(sum(entry.size for entry in removed))}"
    if kept:
        summary += f"; kept {len(kept)} pinned file(s)"
    typer.echo(summary, err=True)


def _echo_entries(found: list[CacheEntry]) -> None:
    """Print dataset id, asset id, size, and retrieval time in aligned columns."""
    rows = [
        (
            entry.dataset_id,
            entry.asset_id,
            _human(entry.size),
            entry.retrieved_at.isoformat() if entry.retrieved_at else "unrecorded",
        )
        for entry in found
    ]
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]) - 1)]
    for row in rows:
        padded = [f"{value:<{width}}" for value, width in zip(row, widths, strict=False)]
        typer.echo("  ".join([*padded, row[-1]]))
    total = sum(entry.size for entry in found)
    typer.echo(f"{len(found)} file(s), {_human(total)}", err=True)
