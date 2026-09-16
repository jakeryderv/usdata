"""The ``inspect`` command: a format-aware summary of one cached file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from usdata.cache import cached_path
from usdata.inspect import Summary, inspect_path

LABELS = ("path", "size", "format", "retrieved", "checksum", "source")
"""Provenance lines printed above the detail, padded to the longest label."""


def inspect(
    target: Annotated[
        str,
        typer.Argument(
            help="Cached file path, or a dataset and asset id as 'noaa:hrrr/<asset id>'."
        ),
    ],
    cache_dir: Annotated[Path | None, typer.Option(help="Override the cache directory.")] = None,
    as_json: Annotated[
        bool, typer.Option("--json", help="Emit the summary as a JSON object and nothing else.")
    ] = False,
) -> None:
    """Show what a fetched file holds: its provenance, its format, and that format's detail."""
    summary = _summarize(_resolve(target, cache_dir))
    if as_json:
        typer.echo(json.dumps(summary.model_dump(mode="json"), indent=2))
        return
    _echo_summary(summary)


def _resolve(target: str, cache_dir: Path | None) -> Path:
    """The file to inspect: the path as given, or where the cache keeps that asset."""
    path = Path(target)
    if path.exists():
        return path
    dataset_id, separator, asset_id = target.rpartition("/")
    if not separator or ":" not in dataset_id:
        typer.secho(f"no file at {target}", err=True, fg="red")
        raise typer.Exit(code=2)
    try:
        return cached_path(dataset_id, asset_id, cache_dir)
    except ValueError as e:
        typer.secho(str(e), err=True, fg="red")
        raise typer.Exit(code=2) from None


def _summarize(path: Path) -> Summary:
    """The summary, or exit 2 when the file or the provenance beside it is unusable."""
    if not path.is_file():
        typer.secho(f"no cached file at {path}", err=True, fg="red")
        raise typer.Exit(code=2)
    try:
        return inspect_path(path)
    except (OSError, ValueError) as e:
        typer.secho(f"no usable provenance beside {path}: {e}", err=True, fg="red")
        raise typer.Exit(code=2) from None


def _echo_summary(summary: Summary) -> None:
    """The provenance block, then a table of whatever detail the format yielded."""
    width = max(len(label) for label in LABELS) + 2
    values = (
        str(summary.path),
        f"{summary.size:,} bytes",
        summary.format.value,
        summary.retrieved_at.isoformat(),
        summary.checksum,
        summary.source_url,
    )
    typer.echo(f"{summary.dataset_id}\n  {summary.asset_id}\n")
    for label, value in zip(LABELS, values, strict=True):
        typer.echo(f"  {label + ':':<{width}}{value}")
    if summary.note:
        typer.secho(f"  {'note:':<{width}}{summary.note}", fg="yellow")
    _echo_detail(summary, width)


def _echo_detail(summary: Summary, width: int) -> None:
    """One table per format: CSV columns, NetCDF variables, or GRIB2 messages."""
    if (frame := summary.csv) is not None:
        counted = f"{frame.row_count:,}"
        if frame.truncated:
            counted = f"at least {counted}, scanned the first {frame.row_limit:,}"
        typer.echo(f"  {'rows:':<{width}}{counted}")
        if not frame.columns:
            typer.echo("  columns: none")
        else:
            typer.echo("  columns:")
            for name in frame.columns:
                typer.echo(f"    {name}")
    if (scene := summary.netcdf) is not None:
        _echo_table(
            "variables",
            ["name", "dims", "shape", "units", "long_name"],
            [
                [
                    variable.name,
                    ", ".join(variable.dims),
                    " x ".join(str(size) for size in variable.shape),
                    variable.units or "",
                    variable.long_name or "",
                ]
                for variable in scene.variables
            ],
        )
    if (fields := summary.grib2) is not None:
        # A partial fetch knows both numberings, so both are printed and labelled.
        in_object = any(message.object_index is not None for message in fields.messages)
        numbering = ["file #", "object #"] if in_object else ["#"]
        _echo_table(
            "messages",
            [*numbering, "shortName", "name", "typeOfLevel", "level", "step", "units", "grid"],
            [
                [
                    str(message.file_index),
                    *([str(message.object_index or "")] if in_object else []),
                    message.short_name or "",
                    message.name or "",
                    message.type_of_level or "",
                    message.level or "",
                    message.step or "",
                    message.units or "",
                    _grid(message.shape),
                ]
                for message in fields.messages
            ],
        )


def _echo_table(label: str, headers: list[str], rows: list[list[str]]) -> None:
    """A padded table under its label, or one line saying the file holds none."""
    if not rows:
        typer.echo(f"  {label}: none")
        return
    widths = [max(len(cell) for cell in column) for column in zip(headers, *rows, strict=True)]
    typer.echo(f"  {label}:")
    for row in (headers, *rows):
        cells = (cell.ljust(size) for cell, size in zip(row, widths, strict=True))
        typer.echo(f"    {'  '.join(cells).rstrip()}")


def _grid(shape: tuple[int, int] | None) -> str:
    """A message's grid as rows by columns, or blank where ecCodes states neither."""
    return "" if shape is None else f"{shape[0]} x {shape[1]}"
