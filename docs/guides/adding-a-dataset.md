# Adding a dataset

A dataset is a registry entry plus an adapter. This guide walks through both
using `noaa:ghcn-daily` as the worked example.

## 1. Check the source

Before writing code, answer these against the live service:

- How are files or records addressed? (bucket layout, REST parameters, ERDDAP grammar)
- Does the server subset by space, time, or variable? This becomes `capabilities`,
  which a contract test holds to the fields the adapter accepts and refuses.
- Is access anonymous? If the source needs a key, declare it under `credentials`
  (see [Adapter](#3-adapter)) and probe it with your own key, never a shared one.
- What is the license? Most federal data is public domain; say so explicitly.

Probe with `curl` and keep the commands; they become the basis of the
integration test.

## 2. Registry entry

Add to `src/usdata/data/registry.yaml`:

```yaml
  - id: noaa:ghcn-daily            # <provider>:<name>, stable forever
    provider: noaa                  # must appear under top-level `providers:`
    system: noaa:ncei-access        # optional: one of the ids under top-level `systems:`
    domain: surface-weather         # one of the ids under top-level `domains:`
    status: available               # planned (no adapter) | available
    since: "0.2"                    # available: version it shipped in
    # target: "0.4" | later         # planned: phase it is aimed at
    title: GHCN-Daily Station Observations
    description: >-                 # what it is, how it is served, what subsetting exists
      ...
    keywords: [climate, precipitation, stations, daily]
    protocol: http                  # http | s3 | erddap
    homepage: https://...
    license: US Government Work (public domain)
    spatial_extent: { west: -180.0, south: -90.0, east: 180.0, north: 90.0 }
    temporal_extent: { start: "1763-01-01T00:00:00Z" }
    capabilities: { spatial_subset: false, temporal_subset: true, variable_subset: true }
    summary: Daily station weather      # <= 80 characters; the title used by docs, site, and CLI
    formats: [CSV]                      # what the files actually are, at least one
    selection: Station observations within inclusive calendar dates; selected elements
    inputs: Both dates; station IDs or a geographic query
    reader: pandas                      # pandas | radar | netcdf | grib, or null for bytes only
    guide: docs/providers/noaa-ghcn.md  # this dataset's own usage guide
    examples:                           # its walkthrough first, then every study using it
      - examples/datasets/noaa-ghcn-daily/noaa-ghcn-daily.ipynb
      - examples/studies/weather-and-streamflow/weather-and-streamflow.ipynb
    resolution:                         # free text, in the source's own words
      spatial: Land surface stations; more than 100,000 stations in 180 countries and territories
      temporal: Daily
    update_frequency: Daily, reconstructed each weekend from more than 25 data source components
    latency: >-                         # omit unless the agency states a figure
      Real-time streams are replaced by archive-ready sources 45 to 60 days after the end of a month
    citation: >-
      Menne, M.J., I. Durre, R.S. Vose, B.E. Gleason, and T.G. Houston, 2012: An overview of the
      Global Historical Climatology Network-Daily Database. Journal of Atmospheric and Oceanic
      Technology, 29, 897-910, doi:10.1175/JTECH-D-11-00103.1
    terms: https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C00861/html
    variables:                          # what the files deliver, with units as delivered
      - { name: PRCP, units: mm, description: "Precipitation total (metric units)" }
      - { name: TMAX, units: "degrees Celsius", description: "Maximum temperature (metric units)" }
    # limits: { max_window: P1D }       # only where the adapter enforces a window
    adapter: usdata.providers.noaa.ghcnd:GhcnDaily
```

Every field must be true. The registry test suite loads all entries and
imports every non-planned adapter. A dataset can start life as `planned`
with just this entry, which puts it in search results and the docs; flip it
to `available` when the live test passes, replacing `target` with `since`. Planned datasets are hidden from `usdata search`
unless `--planned` is passed; `info` always works. Moving a dataset to a different
phase is a one-line change to `target`; the generated versions and catalog pages follow.
Run `just docs` after editing to refresh `docs/generated/catalog/`. The README
and provider index remain handwritten. The entry is the only schema: `summary`,
`formats`, `selection`, `inputs`, `reader`, `guide`, and `examples` feed the
generated reference, the website browser, and `usdata info` from the same place.
A planned entry leaves them out; an implemented one must give a summary, at least
one format, a selection rule, its required inputs, its own usage guide under
`docs/providers/`, and at least one example that exists: its walkthrough in
`examples/datasets/<provider>-<name>/`, listed first, then every study whose
manifest uses it ([ADR 0041](../adr/0041-dataset-walkthroughs-and-studies.md)). `reader` names the extra
that opens the files, or is `null` for a format with no bundled reader. `system`
names the product family or service the dataset comes from, declared under
top-level `systems:` for the same provider, and groups the generated catalog
page; leave it out when the dataset belongs to no family.

The same entry also describes the data itself, and every value must be
traceable to an upstream page listed under **Metadata sources** at the end of
the dataset's guide:

- `resolution.spatial` and `resolution.temporal` are single lines of free text
  in the source's own words: a grid spacing, a station network, a scan cadence.
- `update_frequency` says how often the source publishes, quoting the agency
  where it states a cadence.
- `latency` says how far behind real time the source runs. Use the agency's own
  figure or a range the provider guide already documents; leave it out rather
  than estimating one, and say in the guide that no figure is published.
- `citation` is one line: the form the agency asks for, or an
  "Agency, Product, accessed via usdata" form when it publishes none.
- `terms` is the https URL of the page that states the conditions of use, which
  is often not the homepage.
- `variables` lists what the files deliver, with `units` as delivered rather
  than as converted, and unique names. List the whole set where it is bounded;
  where it is open, such as a GRIB2 file of hundreds of fields, list the handful
  the guide and examples use and say in the entry's `description` that the
  delivered set is open.
- `limits.max_window` is an ISO 8601 duration such as `P1D`, and must equal the
  window constant the adapter enforces; a registry test compares the two.

The generated catalog links each reference to its usage guide and examples;
no manual dataset navigation entry is needed. For a new agency, write access notes in
`docs/providers/<provider>.md` and link its generated catalog. See the
[documentation workflow](documentation.md) for source ownership and preview commands.

## 3. Adapter

Create `src/usdata/providers/<agency>/<name>.py` with a `Provider` subclass.
`usdata.providers` exports everything an adapter is written against -- `Provider`,
`HttpProvider`, `QueryError`, `NotImplementedProvider`, `load_adapter`, and the
parameter coercions -- and [ADR 0027](../adr/0027-provider-contract.md) says what
of it is stable:

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
    reject those fields rather than return unfiltered data. What is rejected
    here is what the entry's `capabilities` may claim: a contract test probes a
    bbox, a variable, and a window against every available adapter, so a
    declared capability the adapter refuses fails the offline suite.
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
  "Required ", becomes the hint in its "is required" message. Declare an optional
  key as a union with `None` (`StrList | None`, `OptionalUpperStrList`), so the
  coercion annotates the value rather than the union: an explicit null then means
  "not given" and falls through to the field default exactly as an absent key
  does, while an empty string or list stays an error. The model is the only
  declaration form, so a subclass extends its parent's parameters by subclassing
  the parent's model, and an adapter that takes no parameters declares none and
  calls `self.check_params(query)`, which then rejects every key.
- Raise `QueryError` with a helpful message when the query lacks something else
  the source needs (a station list, an explicit datum). The CLI turns it into
  exit code 2. Reject empty explicit identifiers and conflicting selectors too;
  do not silently fall back after a typo. Keep the longer prose in the
  module docstring and the provider access notes.
- Use `usdata.protocols.http`, `usdata.protocols.s3`, or `usdata.protocols.erddap` for transport. Take an
  optional `httpx.Client` in `__init__` so tests can inject one. Override
  `close()` to release internally owned resources; injected clients remain the
  caller's responsibility. HTTP adapters inherit `usdata.providers.HttpProvider`
  instead of duplicating that lifecycle: it creates the client on first use
  behind `self._http()`, closes the one it owns, and leaves an injected one to
  its caller. Core uses adapters as context managers. Use
  `http.get(url, client, params=...)` for metadata and `http.download` for bytes
  so retries cover both listing and downloads.
- If the source needs a key, declare it in the registry entry under
  `credentials`: the `variables` it reads, named `USDATA_<SYSTEM>_<FIELD>`, and
  the `signup` URL where the agency issues one. The core reads them from the
  environment and passes them as `credentials=`; the adapter reads
  `self.credentials[NAME]` and never `os.environ`. Add them to each request as
  it is sent, never to an `Asset` field. Merge them into the href with
  `httpx.URL(asset.href).copy_merge_params(...)`: passing `params=` makes httpx
  replace the href's whole query, selection and all. Wrap every such request in
  `with self.redacted_errors():` so a failure cannot print the key. If the
  response echoes the request or differs between identical requests, write a
  canonical form and say how in the `transformations` class attribute. See
  [ADR 0039](https://github.com/jakeryderv/usdata/blob/main/docs/adr/0039-credentialed-sources.md).
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

Add a representative scenario to `tests/adapters/test_contracts.py`: the dataset's
`--param` values in `CASES`, plus whatever its listing needs from
`contract_transport`. The checks themselves live in `usdata.testing` and cover
every available dataset: stable assets, dataset identity, explicit fetch
destinations, exact bytes, no provider cache/sidecars, invalid-input rejection
before client creation, owned/injected cleanup, and the entry's declared
`capabilities` and `limits.max_window`. Source-specific query and pagination
assertions remain in the adapter module.

The same checks run from outside this repository, so an adapter distributed
separately is held to the same contract. Supply the `Dataset`, a factory that
builds the adapter, a scenario query, and a client factory on a mock transport:

```python
from usdata.testing import check_provider_contract


def test_my_adapter(tmp_path) -> None:
    downloads: set[str] = set()
    check_provider_contract(
        MY_DATASET,
        lambda client=None: MyProvider(MY_DATASET, client),
        build_query(start="2024-05-06T12:00Z", end="2024-05-06T12:05Z"),
        client_factory=lambda: httpx.Client(transport=my_transport(downloads)),
        expected_bytes=DATA,
        arm_download=downloads.add,
        work_dir=tmp_path,
    )
```

`check_provider_contract` runs every rule; the individual `check_*` functions it
composes are exported too, for a suite that wants one test per rule. `pytest` is
imported inside them, so it stays a development dependency.

For a dataset that declares `credentials`, the factory also takes
`credentials=`, defaulting to `sentinel_credentials(MY_DATASET)`, and the
contract adds two checks. A missing or blank variable must be refused with
`MissingCredentials` before any client exists. And the sentinel values must
reach the mock transport, yet appear in no asset, fetched byte, httpx log
line, or error raised by a failing fetch. Pass `failing_client_factory` so that
last part runs:

```python
def factory(client=None, credentials=sentinel_credentials(MY_DATASET)):
    return MyKeyedProvider(MY_DATASET, client, credentials=credentials)
```

Live tests read real keys from repository secrets and skip, naming the
variables, when they are unset.

## 5. Docs and changelog

- Write the dataset's walkthrough notebook in `examples/datasets/<provider>-<name>/`,
  following the template in [`examples/README.md`](https://github.com/jakeryderv/usdata/blob/main/examples/README.md#writing-a-walkthrough-or-a-study),
  run it with `just run-notebooks --notebook <provider>-<name> --write`, and
  list it first under the entry's `examples`. It becomes the dataset's page on
  usdata.dev, preview image included.
- Add a CLI example to the README if the dataset introduces a new kind of query.
- Add anything you learned about the source to the access notes in `docs/providers/<provider>.md`.
- Add a [release-note fragment](https://github.com/jakeryderv/usdata/blob/main/changes/README.md) for the new dataset.
- If you made a non-obvious design choice, write an ADR.
