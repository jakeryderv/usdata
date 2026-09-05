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
    status: available               # planned (no adapter) | stub | available
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
to `stub` when the class exists and `available` when the live test passes.
Run `just docs` after editing: the README and reference tables are generated.

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
  and document them in the module docstring.
- Use `usdata.protocols.http` or `usdata.protocols.s3` for transport. Take an
  optional `httpx.Client` in `__init__` so tests can inject one.
- Give assets stable ids: they become cache filenames and lockfile keys.
- Set `size` and `time` on assets when the listing provides them.
- Do not write to the cache or create provenance. `usdata.fetch` does that.

## 4. Tests

- `tests/unit/test_<name>.py`: mock every HTTP call with `respx`. Cover query
  validation, pagination, and the fetch path. These run on every PR.
- `tests/integration/test_<name>_live.py`: mark the module
  `pytestmark = pytest.mark.integration`. Fetch the smallest real object you
  can find. These run weekly.

## 5. Docs and changelog

- Add a CLI example to the README if the dataset introduces a new kind of query.
- Add a line under `Unreleased` in `CHANGELOG.md`.
- If you made a non-obvious design choice, write an ADR.
