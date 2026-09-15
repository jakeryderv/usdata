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
    status: available               # planned (no adapter) | available
    since: "0.2"                    # available: version it shipped in
    # target: "0.4" | later         # planned: phase it is aimed at
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
to `available` when the live test passes, replacing `target` with `since`. Planned datasets are hidden from `usdata search`
unless `--planned` is passed; `info` always works. Moving a dataset to a different
phase is a one-line change to `target`; the generated versions and catalog pages follow.
Run `just docs` after editing to refresh `docs/generated/catalog/`. The README
and provider index remain handwritten. For every implemented dataset, add a
unique usage guide under `docs/providers/` and register its path in the registry
`catalog` mapping, including a short summary, explicit output formats, selection
behavior, required inputs, reader extra, and example paths. The generated catalog links each reference to its usage guide and examples;
no manual dataset navigation entry is needed. For a new agency, write access notes in
`docs/providers/<provider>.md` and link its generated catalog. See the
[documentation workflow](documentation.md) for source ownership and preview commands.

## 3. Adapter

Create `src/usdata/providers/<agency>/<name>.py` with a `Provider` subclass:

```python
class GhcnDaily(Provider):
    params_model = GhcnDailyParams  # The pydantic model declaring `--param` keys.

    def list_assets(self, query: Query) -> list[Asset]:
        """Translate the query into concrete objects. No downloading here."""

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Write one asset to dest. The core handles caching and provenance."""
```

Rules:

- Validate before any transport, using the `Provider` helpers so every adapter
  reports the same mistakes the same way:
  - `self.parse_params(query, YourParams)` validates `query.params` against the
    pydantic model the class declares as `params_model` and returns it typed.
    The model is the whole declaration: its field types and validators say what
    is accepted, its `Field(description=...)` text is what `usdata info` and the
    generated catalog page print, and `accepted_params` is derived from it.
    `tests/adapters/test_contracts.py` checks that every declared key is accepted,
    that an undeclared one is rejected by name, and that a declared model forbids
    extra keys and matches `accepted_params`.
  - `self.reject(query, "text", ...)` names the query fields (`text`, `bbox`,
    `variables`, `time`) the source cannot honour, with a `hint` saying what to
    do instead. No adapter supports free text, and a contract test checks that
    none ignores it; a source that cannot filter by location or variable must
    reject those fields rather than return unfiltered data.
  - `self.utc_window(query)` returns the required start and end in UTC, reading
    naive bounds as UTC. Use `usdata.providers.base.to_utc` for optional bounds.
    A contract test checks that naive and offset bounds resolve like UTC ones.
- Declare the parameters as a model. `query.params` stays an untyped dict on the
  wire, between the CLI, a manifest, and the adapter; typing starts at the
  adapter boundary:

  ```python
  class GhcnDailyParams(BaseModel):
      """What one GHCN-Daily query names."""

      model_config = ConfigDict(extra="forbid")

      stations: StrList = Field(
          description="Required station id(s): one, a list, or comma-separated."
      )
      units: Annotated[str, choice("metric", "standard")] = Field(
          default="metric", description="Unit system: metric (default) or standard."
      )
  ```

  Reuse the coercions in `usdata.providers.params` (`int_range`, `int_list`,
  `choice`, `StrList`) rather than writing new ones: they accept the strings the
  CLI passes, reject the booleans and floats a lax integer would swallow, and
  split comma-separated lists. Cross-field rules, such as a ceiling that depends
  on another parameter, belong in a `model_validator(mode="after")`. Write
  validator messages as the tail of a sentence about the field ("must be sfc,
  prs, or nat"); the field name is prefixed for you, cross-field messages name
  their own subject, and a required field's description, minus a leading
  "Required ", becomes the hint in its "is required" message. Adapters that have
  not migrated yet still hand-parse `query.params` and declare the
  `accepted_params` mapping themselves, with `self.check_params(query)` rejecting
  unknown keys; a subclass extending its parent's mapping spreads it.
- Raise `QueryError` with a helpful message when the query lacks something else
  the source needs (a station list, an explicit datum). The CLI turns it into
  exit code 2. Reject empty explicit identifiers and conflicting selectors too;
  do not silently fall back after a typo. Keep the longer prose in the
  module docstring and the provider access notes.
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
- Add anything you learned about the source to the access notes in `docs/providers/<provider>.md`.
- Add a [release-note fragment](https://github.com/jakeryderv/usdata/blob/main/changes/README.md) for the new dataset.
- If you made a non-obvious design choice, write an ADR.
