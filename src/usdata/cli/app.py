"""Typer application: argument parsing and exit codes only; logic lives in the library."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import httpx
import typer

from usdata import __version__, build_query, default_registry
from usdata._fetch import ChecksumMismatch
from usdata._fetch import fetch as fetch_query
from usdata._progress import batch
from usdata.cli.progress import progress
from usdata.manifest import lockfile_path
from usdata.models import READER_EXTRAS_TEXT, Dataset, Status, describe_duration
from usdata.providers import load_adapter
from usdata.providers.base import NotImplementedProvider
from usdata.pull import EmptySource, ManifestChanged, UnknownDatasets, UpstreamChanged
from usdata.pull import pull as pull_manifest
from usdata.pull import verify as verify_manifest
from usdata.query import UnknownPlace
from usdata.registry import (
    CAPABILITY_NAMES,
    NO_READER,
    STATUS_FILTERS,
    DatasetNotFound,
    SearchResult,
)

app = typer.Typer(
    name="usdata",
    help="Discover, fetch, and track provenance of U.S. public scientific data.",
    no_args_is_help=True,
)


_QUERY_FLAGS = {
    "location": "--location",
    "bbox": "--bbox",
    "lat": "--lat",
    "lon": "--lon",
    "radius_km": "--radius-km",
    "start": "--start",
    "end": "--end",
    "variables": "--vars",
    "text": None,
    "provider": None,
}


_STATUS_HELP = f"Support status to include: {', '.join(STATUS_FILTERS)}."

_ProviderOption = Annotated[str | None, typer.Option(help="Restrict to one provider, e.g. noaa.")]
_DomainOption = Annotated[
    str | None, typer.Option(help="Restrict to one domain, e.g. weather-radar.")
]
_FormatOption = Annotated[
    str | None, typer.Option(help="Delivered format, matched case-insensitively, e.g. csv.")
]
_ReaderOption = Annotated[
    str | None,
    typer.Option(help=f"Reader extra that opens the files ({READER_EXTRAS_TEXT}), or {NO_READER}."),
]
_CapabilityOption = Annotated[
    str | None,
    typer.Option(
        help=f"Server-side capability the dataset declares ({', '.join(CAPABILITY_NAMES)})."
    ),
]
_StatusOption = Annotated[str, typer.Option(help=_STATUS_HELP)]
_SearchStatusOption = Annotated[
    str | None, typer.Option(help=f"{_STATUS_HELP} Supersedes --planned.")
]
_JsonOption = Annotated[
    bool, typer.Option("--json", help="Emit a JSON array of dataset records and nothing else.")
]


def _echo_dataset_table(matches: list[Dataset]) -> None:
    """Print id, status, domain, formats, reader, and summary in aligned columns."""
    rows = [
        (
            ds.id,
            f"{ds.status.value} ({ds.version_label})",
            ds.domain,
            ", ".join(ds.formats) or "-",
            ds.reader or NO_READER,
            ds.summary or ds.title,
        )
        for ds in matches
    ]
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]) - 1)]
    for row in rows:
        padded = [f"{value:<{width}}" for value, width in zip(row, widths, strict=False)]
        typer.echo("  ".join([*padded, row[-1]]))


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"usdata {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version."),
    ] = None,
) -> None:
    """usdata: discover, fetch, and track provenance of U.S. public scientific data."""
    pass


@app.command()
def datasets(
    provider: _ProviderOption = None,
    domain: _DomainOption = None,
    format: _FormatOption = None,
    reader: _ReaderOption = None,
    capability: _CapabilityOption = None,
    status: _StatusOption = "available",
    as_json: _JsonOption = False,
) -> None:
    """List the curated dataset registry, filtered."""
    try:
        matches = default_registry().list(
            provider=provider,
            domain=domain,
            format=format,
            reader=reader,
            capability=capability,
            status=status,
        )
    except ValueError as e:
        typer.secho(str(e), err=True, fg="red")
        raise typer.Exit(code=2) from None
    if as_json:
        typer.echo(json.dumps([ds.model_dump(mode="json") for ds in matches], indent=2))
    elif matches:
        _echo_dataset_table(matches)
    else:
        typer.echo("No datasets matched.")
    if not matches:
        raise typer.Exit(code=1)


@app.command()
def search(
    text: Annotated[str | None, typer.Argument(help="Free-text keywords.")] = None,
    provider: _ProviderOption = None,
    state: Annotated[
        str | None,
        typer.Option("--location", "--state", help="State, 'County, ST', or quoted FIPS code."),
    ] = None,
    start: Annotated[str | None, typer.Option(help="ISO date or datetime.")] = None,
    end: Annotated[str | None, typer.Option(help="ISO date or datetime.")] = None,
    planned: Annotated[
        bool, typer.Option("--planned", help="Include planned datasets that have no adapter yet.")
    ] = False,
    domain: _DomainOption = None,
    format: _FormatOption = None,
    reader: _ReaderOption = None,
    capability: _CapabilityOption = None,
    status: _SearchStatusOption = None,
    as_json: _JsonOption = False,
) -> None:
    """Search the curated dataset registry."""
    try:
        query = build_query(text, provider=provider, location=state, start=start, end=end)
        results = default_registry().search(
            query,
            include_planned=planned,
            domain=domain,
            format=format,
            reader=reader,
            capability=capability,
            status=status,
        )
    except ValueError as e:
        typer.secho(str(e), err=True, fg="red")
        raise typer.Exit(code=2) from None
    if as_json:
        records = [{**r.dataset.model_dump(mode="json"), "score": r.score} for r in results]
        typer.echo(json.dumps(records, indent=2))
    elif results:
        _echo_search_results(results)
    else:
        typer.echo("No datasets matched.")
    if not results:
        raise typer.Exit(code=1)


def _echo_search_results(results: list[SearchResult]) -> None:
    """Print one line per hit: id, status, version label, and title."""
    width = max(len(r.dataset.id) for r in results)
    for r in results:
        ds = r.dataset
        typer.echo(f"{ds.id:<{width}}  {ds.status.value:<9}  {ds.version_label:<12}  {ds.title}")


@app.command()
def info(
    dataset_id: Annotated[str, typer.Argument(help="Dataset id, e.g. noaa:nexrad-level2")],
) -> None:
    """Show details for one dataset."""
    try:
        ds = default_registry().get(dataset_id)
    except DatasetNotFound:
        typer.secho(f"Unknown dataset: {dataset_id}", err=True, fg="red")
        raise typer.Exit(code=2) from None
    typer.echo(f"{ds.id}\n  {ds.title}\n")
    typer.echo(f"  {ds.description.strip()}\n")
    typer.echo(f"  status:    {ds.status.value} ({ds.version_label})")
    typer.echo(f"  domain:    {ds.domain}")
    typer.echo(f"  provider:  {ds.provider}")
    typer.echo(f"  protocol:  {ds.protocol.value}")
    typer.echo(f"  license:   {ds.license or 'unknown'}")
    typer.echo(f"  homepage:  {ds.homepage or '-'}")
    caps = ", ".join(k for k, v in ds.capabilities.model_dump().items() if v) or "none"
    typer.echo(f"  subsetting: {caps}")
    if ds.spatial_extent:
        typer.echo(f"  extent:    {ds.spatial_extent.as_tuple()}")
    if ds.temporal_extent:
        typer.echo(
            f"  time:      {ds.temporal_extent.start} .. {ds.temporal_extent.end or 'present'}"
        )
    if ds.status is not Status.AVAILABLE:
        return  # Planned entries have no adapter or usage metadata to show.
    with load_adapter(ds) as adapter:
        declared = dict(adapter.accepted_params)
    if declared:
        typer.echo("  params:")
        width = max(len(name) for name in declared)
        for name, description in sorted(declared.items()):
            typer.echo(f"    {name:<{width}}  {description}")
    else:
        typer.echo("  params:    none")
    _echo_usage(ds)
    _echo_description(ds)


def _echo_usage(ds: Dataset) -> None:
    """What the dataset delivers and what it takes, from the registry entry."""
    if ds.formats:
        typer.echo(f"  formats:   {', '.join(ds.formats)}")
        typer.echo(f"  reader:    {f'usdata[{ds.reader}]' if ds.reader else 'none'}")
    if ds.selection:
        typer.echo(f"  selection: {ds.selection}")
    if ds.inputs:
        typer.echo(f"  inputs:    {ds.inputs}")
    if ds.examples:
        typer.echo(f"  examples:  {', '.join(ds.examples)}")


def _echo_description(ds: Dataset) -> None:
    """Resolution, cadence, limits, and provenance metadata, each line only when set."""
    if ds.resolution:
        parts = [p for p in (ds.resolution.spatial, ds.resolution.temporal) if p]
        if parts:
            typer.echo(f"  resolution: {'; '.join(parts)}")
    if ds.update_frequency:
        typer.echo(f"  updates:   {ds.update_frequency}")
    if ds.latency:
        typer.echo(f"  latency:   {ds.latency}")
    if ds.limits and ds.limits.max_window:
        typer.echo(f"  limits:    max window {describe_duration(ds.limits.max_window)}")
    if ds.terms:
        typer.echo(f"  terms:     {ds.terms}")
    if ds.citation:
        typer.echo(f"  citation:  {ds.citation}")
    if ds.variables:
        typer.echo("  variables:")
        width = max(len(variable.label) for variable in ds.variables)
        for variable in ds.variables:
            typer.echo(f"    {variable.label:<{width}}  {variable.description or ''}".rstrip())


@app.command()
def fetch(
    dataset_id: Annotated[str, typer.Argument(help="Dataset id, e.g. noaa:ghcn-daily")],
    state: Annotated[
        str | None,
        typer.Option("--location", "--state", help="State, 'County, ST', or quoted FIPS code."),
    ] = None,
    bbox: Annotated[str | None, typer.Option(help="west,south,east,north in degrees.")] = None,
    lat: Annotated[float | None, typer.Option()] = None,
    lon: Annotated[float | None, typer.Option()] = None,
    radius_km: Annotated[float, typer.Option(help="Radius around --lat/--lon.")] = 50.0,
    start: Annotated[str | None, typer.Option(help="ISO date or datetime.")] = None,
    end: Annotated[str | None, typer.Option(help="ISO date or datetime.")] = None,
    variables: Annotated[
        str | None, typer.Option("--vars", help="Comma-separated variable names.")
    ] = None,
    param: Annotated[
        list[str] | None,
        typer.Option("--param", "-p", help="Provider-specific key=value, repeatable."),
    ] = None,
    cache_dir: Annotated[Path | None, typer.Option(help="Override the cache directory.")] = None,
    force: Annotated[bool, typer.Option(help="Re-download even if cached.")] = False,
    no_progress: Annotated[bool, typer.Option(help="Disable terminal progress.")] = False,
    dry_run: Annotated[
        bool, typer.Option(help="List matching assets without downloading.")
    ] = False,
) -> None:
    """Resolve a query against one dataset and download the matching assets."""
    params: dict[str, str] = {}
    for item in param or []:
        key, sep, value = item.partition("=")
        if not sep:
            typer.secho(f"--param expects key=value, got {item!r}", err=True, fg="red")
            raise typer.Exit(code=2)
        if key in _QUERY_FLAGS:
            flag = _QUERY_FLAGS[key]
            hint = (
                f"use {flag} instead of --param"
                if flag is not None
                else "fetch does not support this option"
            )
            typer.secho(
                f"{key} is a reserved query option; {hint}",
                err=True,
                fg="red",
            )
            raise typer.Exit(code=2)
        params[key] = value
    box = None
    if bbox:
        try:
            w, s, e, n = (float(x) for x in bbox.split(","))
        except ValueError:
            typer.secho("--bbox expects west,south,east,north", err=True, fg="red")
            raise typer.Exit(code=2) from None
        box = (w, s, e, n)
    try:
        ds = default_registry().get(dataset_id)
        query = build_query(
            location=state,
            bbox=box,
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            start=start,
            end=end,
            variables=[v.strip() for v in variables.split(",")] if variables else None,
            **params,
        )
        if dry_run:
            with load_adapter(ds) as adapter:
                assets = adapter.list_assets(query)
            for a in assets:
                typer.echo(f"{a.id}\t{a.href}")
            typer.echo(f"{len(assets)} asset(s) matched", err=True)
            with progress(disabled=no_progress):
                batch([asset.size for asset in assets])
            return
        with progress(disabled=no_progress):
            fetched = fetch_query(ds, query, root=cache_dir, force=force)
    except (DatasetNotFound, UnknownPlace, ValueError) as e:
        typer.secho(str(e), err=True, fg="red")
        raise typer.Exit(code=2) from None
    except NotImplementedProvider as e:
        typer.secho(str(e), err=True, fg="yellow")
        raise typer.Exit(code=3) from None
    except (httpx.HTTPError, ChecksumMismatch) as e:
        typer.secho(f"request failed: {e}", err=True, fg="red")
        raise typer.Exit(code=4) from None
    if not fetched:
        typer.echo("No assets matched.", err=True)
        raise typer.Exit(code=1)
    for f in fetched:
        tag = "cached" if f.from_cache else "fetched"
        typer.echo(f"{f.path}\t{tag}\t{f.provenance.size} bytes")


@app.command()
def pull(
    manifest: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    cache_dir: Annotated[Path | None, typer.Option(help="Override the cache directory.")] = None,
    force: Annotated[
        bool,
        typer.Option(help="Ignore an existing lockfile: re-resolve every source and rewrite it."),
    ] = False,
    update: Annotated[
        list[str] | None,
        typer.Option(
            help="Asset or dataset id whose pin should follow current upstream bytes; repeatable."
        ),
    ] = None,
    no_progress: Annotated[
        bool, typer.Option("--no-progress", help="Disable terminal progress.")
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Print only the summary line, not one line per asset."),
    ] = False,
) -> None:
    """Fetch every source in a manifest and write (or restore from) its lockfile."""
    try:
        with progress(disabled=no_progress):
            result = pull_manifest(manifest, root=cache_dir, force=force, update=update or [])
    except EmptySource as e:
        typer.secho(str(e), err=True, fg="yellow")
        raise typer.Exit(code=1) from None
    except (DatasetNotFound, UnknownDatasets, ManifestChanged, UnknownPlace, ValueError) as e:
        typer.secho(str(e), err=True, fg="red")
        raise typer.Exit(code=2) from None
    except NotImplementedProvider as e:
        typer.secho(str(e), err=True, fg="yellow")
        raise typer.Exit(code=3) from None
    except UpstreamChanged as e:
        for d in e.drift:
            typer.echo(f"{d.asset_id}\t{d.problem}\t{d.path}")
        typer.secho(
            f"{len(e.drift)} asset(s) changed upstream; lockfile unchanged. "
            "Pass --update <asset or dataset id> to accept the new bytes.",
            err=True,
            fg="red",
        )
        raise typer.Exit(code=4) from None
    except (httpx.HTTPError, ChecksumMismatch) as e:
        typer.secho(f"fetch failed: {e}", err=True, fg="red")
        raise typer.Exit(code=4) from None
    updated = set(result.updated)
    if not quiet:
        for f in result.fetched:
            tag = "updated" if f.asset.id in updated else "cached" if f.from_cache else "fetched"
            typer.echo(f"{f.path}\t{tag}\t{f.provenance.size} bytes")
    if result.updated:
        mode = f"updated {len(result.updated)} pin(s) in"
    else:
        mode = "restored from" if result.from_lockfile else "wrote"
    typer.echo(f"{len(result.fetched)} asset(s); {mode} {result.lockfile_path}", err=True)


@app.command()
def verify(
    manifest: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    cache_dir: Annotated[Path | None, typer.Option(help="Override the cache directory.")] = None,
) -> None:
    """Check cached files against a manifest's lockfile. Exit 1 on any drift."""
    lock = lockfile_path(manifest)
    if not lock.exists():
        typer.secho(f"no lockfile at {lock}; run pull first", err=True, fg="red")
        raise typer.Exit(code=2)
    try:
        drift = verify_manifest(manifest, root=cache_dir)
    except (ManifestChanged, ValueError, OSError) as e:
        typer.secho(str(e), err=True, fg="red")
        raise typer.Exit(code=2) from None
    for d in drift:
        typer.echo(f"{d.asset_id}\t{d.problem}\t{d.path}")
    if drift:
        typer.secho(f"{len(drift)} asset(s) drifted from {lock.name}", err=True, fg="red")
        raise typer.Exit(code=1)
    typer.echo(f"all assets match {lock.name}", err=True)
