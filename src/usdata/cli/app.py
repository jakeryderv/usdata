from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from usdata import __version__, build_query, default_registry
from usdata.manifest import Manifest
from usdata.providers import load_adapter
from usdata.providers.base import NotImplementedProvider
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
) -> None:
    """Search the curated dataset registry."""
    try:
        query = build_query(text, provider=provider, location=state, start=start, end=end)
    except UnknownPlace as e:
        typer.secho(f"Unknown place: {e}", err=True, fg="red")
        raise typer.Exit(code=2) from None
    results = default_registry().search(query)
    if not results:
        typer.echo("No datasets matched.")
        raise typer.Exit(code=1)
    width = max(len(r.dataset.id) for r in results)
    for r in results:
        typer.echo(f"{r.dataset.id:<{width}}  {r.dataset.title}")


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
    dataset_id: Annotated[str, typer.Argument(help="Dataset id, e.g. noaa:nexrad-level2")],
    state: Annotated[str | None, typer.Option(help="State name or postal code.")] = None,
    lat: Annotated[float | None, typer.Option()] = None,
    lon: Annotated[float | None, typer.Option()] = None,
    start: Annotated[str | None, typer.Option(help="ISO date or datetime.")] = None,
    end: Annotated[str | None, typer.Option(help="ISO date or datetime.")] = None,
) -> None:
    """Resolve a query against one dataset and download the matching assets."""
    try:
        ds = default_registry().get(dataset_id)
        query = build_query(location=state, lat=lat, lon=lon, start=start, end=end)
        assets = load_adapter(ds).list_assets(query)
    except (DatasetNotFound, UnknownPlace, ValueError) as e:
        typer.secho(str(e), err=True, fg="red")
        raise typer.Exit(code=2) from None
    except NotImplementedProvider as e:
        typer.secho(str(e), err=True, fg="yellow")
        raise typer.Exit(code=3) from None
    typer.echo(f"{len(assets)} asset(s) matched")


@app.command()
def pull(manifest: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]) -> None:
    """Fetch every source in a manifest and write a lockfile."""
    m = Manifest.load(manifest)
    missing = m.validate_against()
    if missing:
        typer.secho(f"Unknown datasets in manifest: {', '.join(missing)}", err=True, fg="red")
        raise typer.Exit(code=2)
    typer.echo(f"{m.name} v{m.version}: {len(m.sources)} source(s) validated")
    typer.secho("pull is not implemented yet; no data was fetched.", err=True, fg="yellow")
    raise typer.Exit(code=3)
