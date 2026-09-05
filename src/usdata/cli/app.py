"""Typer application: argument parsing and exit codes only; logic lives in the library."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import httpx
import typer

from usdata import __version__, build_query, default_registry
from usdata.fetch import ChecksumMismatch
from usdata.fetch import fetch as fetch_query
from usdata.manifest import lockfile_path
from usdata.providers import load_adapter
from usdata.providers.base import NotImplementedProvider
from usdata.pull import EmptySource, ManifestChanged, UnknownDatasets
from usdata.pull import pull as pull_manifest
from usdata.pull import verify as verify_manifest
from usdata.query import UnknownPlace
from usdata.registry import DatasetNotFound

app = typer.Typer(
    name="usdata",
    help="Discover, fetch, and track provenance of U.S. public scientific data.",
    no_args_is_help=True,
)


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
def search(
    text: Annotated[str | None, typer.Argument(help="Free-text keywords.")] = None,
    provider: Annotated[
        str | None, typer.Option(help="Restrict to one provider, e.g. noaa.")
    ] = None,
    state: Annotated[str | None, typer.Option(help="State name or postal code.")] = None,
    start: Annotated[str | None, typer.Option(help="ISO date or datetime.")] = None,
    end: Annotated[str | None, typer.Option(help="ISO date or datetime.")] = None,
    planned: Annotated[
        bool, typer.Option("--planned", help="Include planned datasets that have no adapter yet.")
    ] = False,
) -> None:
    """Search the curated dataset registry."""
    try:
        query = build_query(text, provider=provider, location=state, start=start, end=end)
    except ValueError as e:
        typer.secho(str(e), err=True, fg="red")
        raise typer.Exit(code=2) from None
    results = default_registry().search(query, include_planned=planned)
    if not results:
        typer.echo("No datasets matched.")
        raise typer.Exit(code=1)
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


@app.command()
def fetch(
    dataset_id: Annotated[str, typer.Argument(help="Dataset id, e.g. noaa:ghcn-daily")],
    state: Annotated[str | None, typer.Option(help="State name or postal code.")] = None,
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
            return
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
) -> None:
    """Fetch every source in a manifest and write (or restore from) its lockfile."""
    try:
        result = pull_manifest(manifest, root=cache_dir, force=force)
    except EmptySource as e:
        typer.secho(str(e), err=True, fg="yellow")
        raise typer.Exit(code=1) from None
    except (DatasetNotFound, UnknownDatasets, ManifestChanged, UnknownPlace, ValueError) as e:
        typer.secho(str(e), err=True, fg="red")
        raise typer.Exit(code=2) from None
    except NotImplementedProvider as e:
        typer.secho(str(e), err=True, fg="yellow")
        raise typer.Exit(code=3) from None
    except (httpx.HTTPError, ChecksumMismatch) as e:
        typer.secho(f"fetch failed: {e}", err=True, fg="red")
        raise typer.Exit(code=4) from None
    for f in result.fetched:
        tag = "cached" if f.from_cache else "fetched"
        typer.echo(f"{f.path}\t{tag}\t{f.provenance.size} bytes")
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
