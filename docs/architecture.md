# Architecture

## Data flow

```text
user arguments ─► build_query ─► Query
                                   │
        Registry.search(Query) ◄───┤   ranks curated Dataset entries
                                   │
   load_adapter(Dataset) ─► Provider.list_assets(Query) ─► [Asset]
                                   │
                Provider.fetch(Asset, dest) ─► local file
                                   │
             provenance.record ─► Provenance sidecar (.provenance.json)
                                   │
                  Manifest ─► pull ─► Lockfile (assets + provenance)
```

## Components

| Module | Responsibility |
|---|---|
| `models` | Pydantic types shared everywhere: `BBox`, `TimeRange`, `Dataset`, `Query`, `Asset`, `Provenance`. STAC-shaped: Dataset is a Collection, Asset is a file-level Asset. |
| `registry` | Loads the curated `data/registry.yaml`; keyword-ranked search filtered by provider, space, and time. |
| `query` | Turns loose user input (state names, ISO dates, lat/lon) into a normalized `Query`. Place lookup uses `data/places.yaml`. |
| `providers` | One `Provider` subclass per dataset, loaded by dotted path from the registry entry. Translates `Query` to agency-specific listing and download. |
| `cache` | Cache directory resolution and content hashing. |
| `provenance` | Builds and persists a `Provenance` record beside each fetched file. |
| `manifest` | `Manifest` (declared inputs) and `Lockfile` (what was actually fetched, with checksums). |
| `cli` | Typer app. Thin: argument parsing and exit codes only, no logic. |

Planned but not yet present: a `protocols/` package with shared HTTP, S3, and
ERDDAP clients once two adapters need the same one.

## Boundaries

- **Core never imports a provider.** Adapters are reached only through `load_adapter`, so new sources are additive.
- **Providers never touch the cache or write provenance.** They resolve queries to assets and fetch bytes to a path they are given. The core wraps that with caching and provenance so every source gets it for free.
- **The registry is data, not code.** Adding a dataset is a YAML entry plus an adapter class.
- **Search is over the registry, not live catalogs.** See ADR 0001.
- **Heavy scientific dependencies are optional.** Core depends on pydantic, pyyaml, and typer. Anything that opens data (xarray, pandas, geopandas, Py-ART) lives behind extras.

## CLI exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | no results |
| 2 | bad input (unknown dataset, place, or manifest error) |
| 3 | operation not implemented yet |
