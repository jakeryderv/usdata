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
| `query` | Turns loose user input (state/county names, FIPS, ISO dates, lat/lon) into a normalized `Query`. Place lookup uses `data/places.csv`. |
| `providers` | One `Provider` subclass per dataset, loaded by dotted path from the registry entry. Translates `Query` to agency-specific listing and download. |
| `protocols` | Transport clients with no dataset knowledge. `http.download` streams to disk atomically; `s3.list_objects` paginates ListObjectsV2 anonymously. |
| `fetch` | Core loop: adapter resolves assets, cache is checked, bytes fetched, provenance written. |
| `readers` | Local CSV opening behind the pandas extra; media/protocol dispatch, units and source metadata, no fetching or cache writes. |
| `cache` | Cache directory resolution and content hashing. |
| `provenance` | Builds and persists a `Provenance` record beside each fetched file. |
| `manifest` | `Manifest` (declared inputs) and `Lockfile` (what was actually fetched, with checksums). |
| `pull` | Resolve a manifest through adapters and write the lockfile, or restore exactly what a lockfile pins; `verify` re-hashes against it. |
| `cli` | Typer app. Thin: argument parsing and exit codes only, no logic. |

Provider-specific knowledge (endpoints, auth, quirks) lives in `docs/providers/<id>.md`, not here.

`protocols/` holds transport clients shared by adapters. `http` streams
downloads; `s3` lists and reads public buckets over plain HTTPS with no AWS SDK.
`erddap` reads grid metadata/axes and builds coordinate-based CSV subset URLs. `fetch` is the core loop that ties adapter,
cache, and provenance together; the CLI calls it rather than adapters directly.

## Boundaries

- **Core never imports a provider.** Adapters are reached only through `load_adapter`, so new sources are additive.
- **Providers never touch the cache or write provenance.** They resolve queries to assets and fetch bytes to a path they are given. The core wraps that with caching and provenance so every source gets it for free.
- **The registry is data, not code.** Adding a dataset is a YAML entry plus an adapter class. Entries carry a `status`; planned ones have no adapter and exist so search, docs, and the roadmap agree.
- **Search is over the registry, not live catalogs.** See ADR 0001.
- **Heavy scientific dependencies are optional.** Core depends on pydantic, pyyaml, typer, and httpx. Anything that opens data (xarray, pandas, geopandas, Py-ART) lives behind extras.

## CLI exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | no results, a required manifest source is empty, or cached assets drifted |
| 2 | bad input (unknown dataset, place, or manifest error) |
| 3 | operation not implemented yet |
| 4 | upstream request failed |

## Failure boundaries

A manifest source must resolve to assets unless it sets `allow_empty: true`.
A failed resolution leaves an existing lockfile untouched, although earlier
successful downloads remain cached. Restore and verify both check the exact
manifest checksum before trusting its lockfile. See the
[manifest reference](reference/manifests.md) for the reproducibility contract.

`protocols.http.get` and `download` share a bounded retry policy for transient
GET failures. Metadata retries preserve the original request; download retries
restart with a new temporary file. Provider code uses these helpers with its
owned or injected client. Transport remains independent of dataset semantics.

`FetchedAsset.open()` delegates to `readers` on demand. It does not change models,
lockfiles, source bytes, or sidecars. Format selection uses the asset rather than
a current registry lookup, so restored results remain readable. See the
[reader reference](reference/readers.md) and [ADR 0006](adr/0006-optional-local-csv-readers.md).
