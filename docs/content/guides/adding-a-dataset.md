# Adding a dataset

A dataset is a registry entry plus an adapter. This guide walks through both
using `noaa:ghcn-daily` as the worked example.

## 1. Check the source

Before writing code, answer these against the live service:

- How are files or records addressed? (bucket layout, REST parameters, ERDDAP grammar)
- Does the server subset by space, time, or variable? This becomes `capabilities`.
- Is access anonymous? Datasets needing credentials are not yet supported.
- What is the license? Most federal data is public domain; say so explicitly.

Probe with `curl` and keep the commands; they become the basis of the
integration test.

## 2. Registry entry

Add to `src/usdata/data/registry.yaml`:

```yaml
  - id: noaa:ghcn-daily            # <provider>:<name>, stable forever
    provider: noaa                  # must appear under top-level `providers:`
    domain: surface-weather         # one of the ids under top-level `domains:`
    status: available               # planned (no adapter) | stub | available
    since: "0.2"                    # available: version it shipped in
    # target: "0.4" | later         # planned/stub: phase it is aimed at
    title: GHCN-Daily Station Observations
    description: >-                 # what it is, how it is served, what subsetting exists
      ...
    keywords: [climate, precipitation, stations, daily]
    protocol: http                  # http | s3 | erddap | opendap | thredds
    homepage: https://...
    license: US Government Work (public domain)
    spatial_extent: { west: -180.0, south: -90.0, east: 180.0, north: 90.0 }
    temporal_extent: { start: "1763-01-01T00:00:00Z" }
    capabilities: { spatial_subset: false, temporal_subset: true, variable_subset: true }
    adapter: usdata.providers.noaa.ghcnd:GhcnDaily
```

Every field must be true. The registry test suite loads all entries and
imports every non-planned adapter. A dataset can start life as `planned`
with just this entry, which puts it in search results and the docs; flip it
to `stub` when the class exists and `available` when the live test passes,
replacing `target` with `since`. Planned datasets are hidden from `usdata search`
unless `--planned` is passed; `info` always works. Moving a dataset to a different
phase is a one-line change to `target`; the generated versions and catalog pages follow.
Run `just docs` after editing to refresh `docs/content/generated/catalog/`. The README
and provider index remain handwritten. For every implemented dataset, add a
unique usage guide under `docs/content/providers/` and register its path in the registry
`catalog` mapping, including a short summary, explicit output formats, selection
behavior, required inputs, reader extra, and example paths. The site generates
navigation and combines the guide with the reference; no manual dataset nav entry
is needed. For a new agency, write access notes in
`docs/content/providers/<provider>.md` and link its generated catalog. See the
[documentation workflow](documentation.md) for source ownership and preview commands.

## 3. Adapter

Create `src/usdata/providers/<agency>/<name>.py` with a `Provider` subclass:

```python
class GhcnDaily(Provider):
    def list_assets(self, query: Query) -> list[Asset]:
        """Translate the query into concrete objects. No downloading here."""

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Write one asset to dest. The core handles caching and provenance."""
```

Rules:

- Raise `QueryError` with a helpful message when the query lacks something the
  source needs (a time window, a station list). The CLI turns it into exit code 2.
- Accept provider-specific inputs through `query.params` (`stations=`, `site=`)
  and document them in the module docstring and provider access notes. Reject
  unknown parameters, empty explicit identifiers, and conflicting selectors with
  `QueryError`; do not silently fall back after a typo.
- Use `usdata.protocols.http`, `usdata.protocols.s3`, or `usdata.protocols.erddap` for transport. Take an
  optional `httpx.Client` in `__init__` so tests can inject one. Override
  `close()` to release internally owned resources; injected clients remain the
  caller's responsibility. HTTP adapters may inherit the internal
  `providers._http._HttpProvider` lifecycle instead of duplicating it.
  Core uses adapters as context managers. Use
  `http.get(url, client, params=...)` for metadata and `http.download` for bytes
  so retries cover both listing and downloads.
- Give assets stable ids: they become cache filenames and lockfile keys.
- Set `size` and `time` on assets when the listing provides them.
- Do not write to the cache or create provenance. `usdata.fetch` does that.

## 4. Tests

- `tests/adapters/test_<name>.py`: mock every HTTP call with `respx`. Cover query
  validation, pagination, and the fetch path. These run on every PR; real network connections are blocked automatically.
- `tests/live/test_<name>_live.py`: mark the module
  `pytestmark = pytest.mark.live`. Fetch the smallest real object you
  can find. These run weekly.
- Apply the level and dependency rules in [Testing](../testing.md); mark local
  filesystem scenarios `l2` even within an adapter module.

Add a representative scenario to `tests/adapters/test_contracts.py`. Its shared
checks cover every available dataset: stable assets, dataset identity, explicit
fetch destinations, exact bytes, no provider cache/sidecars, invalid-input
rejection before client creation, and owned/injected cleanup. Source-specific
query and pagination assertions remain in the adapter module.

## 5. Docs and changelog

- Add a CLI example to the README if the dataset introduces a new kind of query.
- Add anything you learned about the source to the access notes in `docs/content/providers/<provider>.md`.
- Add a [release-note fragment](../../../changes/README.md) for the new dataset.
- If you made a non-obvious design choice, write an ADR.
