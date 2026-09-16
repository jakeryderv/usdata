# Roadmap

## Why

U.S. agencies publish scientific data through different portals, protocols, and
formats. usdata provides shared discovery, acquisition, and provenance so analyses
can declare and preserve their inputs: a manifest names them, a lockfile pins
them, and the record of what was fetched is what a methods section cites.
Scientific transformation and downstream publishing remain the caller's
responsibility; data is handed to pandas, xarray, and their ecosystems.

## How we plan

Priorities depend on user value, scope, and readiness. Now, Next, and Later do
not imply dates, deadlines, or promised release versions.

- **Now:** selected work with bounded scope and acceptance criteria. Its issue
  records any decisions or dependencies that must be resolved before implementation.
- **Next:** candidates that need investigation or scoping before selection.
- **Later:** retained ideas without an implementation commitment.

Move work into Now when its user benefit, scope, exclusions, acceptance criteria,
and open questions are clear enough to act on. Resolve blocking decisions before
starting dependent work. Keep one or two workstreams active at a time; selecting
an item does not mean implementation has started. Return it to Next or Later if
its priority or readiness changes.

This roadmap records priorities and their rationale. Linked issues hold the
detailed scope, evidence, and completion criteria; implementation proceeds through
focused PRs. When work is complete, close its issue and remove it from active
priorities. Release useful completed work when ready; assign the release version
during release preparation rather than making backlog items wait for a planned
batch. Completed work remains visible in issues and the changelog.

Use the [dataset catalog](providers/README.md) for implemented coverage,
[generated versions and targets](generated/catalog/versions.md) for registry plans,
and [changelog](https://github.com/jakeryderv/usdata/blob/main/CHANGELOG.md) for completed work. Current validation results
belong in [CI](https://github.com/jakeryderv/usdata/actions/workflows/ci.yml) and
[live checks](https://github.com/jakeryderv/usdata/actions/workflows/integration.yml).

## Now

The homepage at [usdata.dev](https://usdata.dev/) and current documentation at
[docs.usdata.dev](https://docs.usdata.dev/) have separate automatic deployments.
The R2 bucket is reserved for dataset storage at `data.usdata.dev`; connecting it
does not implement an SDK remote cache. See
[website operations](guides/website-operations.md) and
[ADR 0015](adr/0015-separate-sites-and-data-storage.md).

The tornado research workstream, tracked in
[issue 118](https://github.com/jakeryderv/usdata/issues/118), shipped complete
in v0.15.0: GLM lightning detections, SPC tornado reports, NEXRAD Level III
products without a reader, a GRIB2 reader extra on ecCodes
([ADR 0022](adr/0022-grib2-reader-backend.md)), MRMS gridded radar products,
HRRR and GFS model output, and the
[tornado classification example](https://usdata.dev/examples/tornado-classification/).
The [worked examples](https://usdata.dev/examples/) are the usage record for a
release: each one states the question it answers and what was awkward while
answering it ([ADR 0025](adr/0025-examples-as-usage-review.md)). The grib extra
is still unchecked on macOS, where ecCodes must be installed separately.

The selected workstream is one registry schema, verified against the adapters
([ADR 0026](adr/0026-one-registry-schema.md)), in three PRs:

- [Fold the catalog block into dataset entries](https://github.com/jakeryderv/usdata/issues/160).
  Done when the `catalog` block is gone, the generators read the model,
  `usdata info` prints formats, reader, selection, and inputs, and the generated
  catalog and website catalog are unchanged apart from field order.
- [Dataset metadata fields](https://github.com/jakeryderv/usdata/issues/161):
  resolution, update frequency, latency, citation, terms, variables, and limits.
  Done when every available dataset fills the fields that apply, with the
  upstream source of each value in the provider notes, and `info` and the
  catalog pages render them.
- [Contract test for capabilities and limits](https://github.com/jakeryderv/usdata/issues/162).
  Done when a registry claim the adapter does not honour fails the offline
  suite, and the MRMS entry is corrected
  ([#158](https://github.com/jakeryderv/usdata/issues/158)).

The [dataset browser](https://usdata.dev/datasets/) provides search, support
and agency filters, selection rules, and links to examples, including the
[2024 climate comparison](https://usdata.dev/examples/climate-anomalies/).

## Next

These follow the schema work and are ordered by what each unblocks. Each has an
issue with the scope to settle before it moves to Now.

- Discovery: a [`datasets` listing and shared search filters with JSON output](https://github.com/jakeryderv/usdata/issues/163),
  and [sizes on `--dry-run`](https://github.com/jakeryderv/usdata/issues/157).
- Diagnostics: [`usdata doctor`](https://github.com/jakeryderv/usdata/issues/164),
  [`usdata cache`](https://github.com/jakeryderv/usdata/issues/165), and
  [`usdata inspect`](https://github.com/jakeryderv/usdata/issues/166) with a
  GRIB2 inventory as data.
- Readers: a [strict `select`](https://github.com/jakeryderv/usdata/issues/167)
  and [units from registry variables](https://github.com/jakeryderv/usdata/issues/168).
- Manifests: [named sources](https://github.com/jakeryderv/usdata/issues/169)
  and [`usdata cite`](https://github.com/jakeryderv/usdata/issues/170).
- Contract: a [public `HttpProvider`, a `usdata.testing` fixture, and an ADR naming the stable surface](https://github.com/jakeryderv/usdata/issues/171),
  and the [registry `system` field](https://github.com/jakeryderv/usdata/issues/172).
- One [flagship severe-weather case study](https://github.com/jakeryderv/usdata/issues/173)
  with Storm Events in its manifest, absorbing the role of the seven small
  tornado examples.
- [Scope GRIB2 partial fetch through index files](https://github.com/jakeryderv/usdata/issues/174):
  acquisition, not analysis, and the largest bandwidth win available for
  model output. Scoping only until pinning and provenance are decided.
- [Housekeeping from the first question-first notebooks](https://github.com/jakeryderv/usdata/issues/175).

Investigate these bounded website additions before selecting
implementation work:

- One bounded exploration workflow backed by R2: publish an example's exact
  inputs, manifest, provenance, checksums, and lightweight preview files. Show the
  previews in the website and link to downloads and SDK instructions. Define
  stable object identities and retention before publishing; reuse identical bytes
  rather than duplicating files for every package release.

These are unscheduled candidates without deadlines or release assignments.
Published example inputs have stable retention and remain separate from disposable
SDK cache entries and from mirroring entire sources. General remote caching stays
in Later until lookup, freshness, upload ownership, and eviction are defined.

Scope one dataset expansion around a concrete analysis use case. These are
candidates to investigate, not selected implementations. Refine a candidate into
an issue with a verified endpoint, bounded example, and acceptance criteria before
moving it to Now. Prefer additions that exercise a useful new access pattern or
reuse an existing one while preserving the adapter, transport, cache/provenance,
and optional-reader boundaries:

- Further NCEI Access Data Service datasets, such as hourly normals.
- Bulk directories and archives, such as IBTrACS.
- Additional GOES ABI products and sectors, and CO-OPS currents.
- Geospatial readers when a supported dataset and representative fixtures justify them.
- A NEXRAD Level III reader, once the bytes-only adapter has a concrete decoding use case.

## Later

- [NASA access through earthaccess](https://github.com/jakeryderv/usdata/issues/9):
  establish credential ownership and authentication behavior first.
- [Remote cache backends](https://github.com/jakeryderv/usdata/issues/11):
  define lookup, freshness, trusted upload ownership, and eviction while preserving
  checksum, provenance, restoration, and published-file retention contracts.
- NetCDF CDRs and static grids.
- Geospatial severe-weather sources that share one blocker: NWS damage survey
  points and polygons (an ArcGIS REST service), the NWS watch and warning
  archive and SPC convective outlooks (shapefiles), and NLCD land cover and 3DEP
  elevation (rasters). None can ship without a geospatial reader and, for the
  damage surveys, an ArcGIS REST transport. Damage surveys plus the warning
  archive would justify that decision: together they give true tornado path
  geometry and warning verification for the labels the package already serves.
- SPC mesoanalysis archives: images only, not machine-readable data.
- Further agencies, live catalog discovery, and third-party registry extensions.
- Format normalization and place-name lookup beyond states and counties.
- A hosted data API or substantial ingestion/analysis jobs when a concrete use
  case requires them. Reassess Railway for a conventional Python/container
  backend at that point; Cloudflare can continue hosting the sites, DNS, and R2.
- Anything that is analysis rather than acquisition: nearest-grid-point and
  concatenation helpers, CRS objects, plotting, and dataframe abstractions.
  Examples document the pandas and xarray idioms instead.
- Third-party adapters discovered through entry points, until the provider
  contract is published and one adapter exists outside this repository.

Deferred issues have no assigned release or date. A registry dataset target of
`later` carries no release commitment; moving a candidate into Now does not
require assigning it a target version.
