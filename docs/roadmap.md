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
The R2 bucket at `data.usdata.dev` is reserved for dataset storage; see
[website operations](guides/website-operations.md) and
[ADR 0015](adr/0015-separate-sites-and-data-storage.md).

Shipped through v0.22.0: the tornado research inputs
([issue 118](https://github.com/jakeryderv/usdata/issues/118)), one registry
schema verified against the adapters
([ADR 0026](adr/0026-one-registry-schema.md)), the published provider contract
([ADR 0027](adr/0027-provider-contract.md)), partial GRIB2 fetch through index
files ([ADR 0028](adr/0028-partial-grib2-fetch-through-index-files.md)),
`doctor`, `cache`, `inspect`, and `cite`, named manifest sources, priced
dry runs, and the
[severe-weather case study](https://usdata.dev/examples/severe-weather-case-study/)
that absorbs the smaller tornado examples. The
[worked examples](https://usdata.dev/examples/) are the usage record for a
release: each one states the question it answers and what was awkward while
answering it ([ADR 0025](adr/0025-examples-as-usage-review.md)). The grib extra
is still unchecked on macOS, where ecCodes must be installed separately.

The last workstream, reproducible inputs in fact rather than in documentation,
is complete. The six archive-backed examples commit their lockfiles and a
weekly job restores each into an empty cache
([ADR 0029](adr/0029-committed-example-lockfiles.md)); a content-addressed
mirror serves pinned bytes after an agency stops serving them
([ADR 0030](adr/0030-content-addressed-mirror.md)); a date alone as an `end`
means the whole UTC day; and `PullResult.one` with a promised order within a
source closed the remaining friction from the case study. The review that
followed tightened the same contract from the other side: a `pull` that fails
for any reason now leaves the lockfile as it was and every cached file either
absent or matching it
([ADR 0031](adr/0031-staged-refresh-and-lockfile-first-commit.md)), and
settled byte ranges are handed to the adapter rather than read back from it
([ADR 0032](adr/0032-fetch-partial.md)).

The first source keyed by place rather than by a box shipped in v0.21.0:
[FEMA disaster declarations](https://github.com/jakeryderv/usdata/issues/241),
whose rows carry state and county FIPS codes and no coordinates. A query now
keeps the place a location resolved
([ADR 0034](adr/0034-query-keeps-the-resolved-place.md)), and the adapter's
window and place rules are in
[ADR 0035](adr/0035-openfema-window-and-place-rules.md). Its
[worked example](https://usdata.dev/examples/disaster-declarations/) joins an
evening's tornado counties to the declaration in force.

The sibling tables of two datasets already in the catalog shipped in v0.22.0,
each chosen with a `table` parameter: the Storm Events
[fatalities and locations tables](https://github.com/jakeryderv/usdata/issues/133),
which join to details on `EVENT_ID`, and the SPC
[hail and wind databases](https://github.com/jakeryderv/usdata/issues/134),
which start in 1955 where the tornado database starts in 1950.

The second source selected by place shipped in v0.22.0 too:
[NWS watches and warnings by county](https://github.com/jakeryderv/usdata/issues/252),
from the Iowa Environmental Mesonet's mirror of NWS products. Beside the Storm
Events reports it answers a question the catalog cannot ask today, how long
before a tornado its warning was issued. It is also the test of whether
[ADR 0034](adr/0034-query-keeps-the-resolved-place.md) generalizes, and scoping
it has already found a gap: a county's code there needs the state's postal
code, which `Place` did not carry and now does. Its window and county rules are in
[ADR 0036](adr/0036-nws-events-by-issuance-and-county.md), and its
[worked example](https://usdata.dev/examples/warning-lead-time/) finds the
warning in effect when the Osage County EF4 began. No workstream is selected.

Available from source for the unreleased v0.23.0: hourly normals through `period: hourly` on
`noaa:climate-normals`, with a one-airport
[hourly temperature comparison](https://usdata.dev/examples/hourly-anomalies/).
The extension preserves calendar-day selection and local-standard-time labels
([ADR 0037](adr/0037-hourly-normals-calendar-days.md)); the example makes its
ten-minute observation matching tolerance explicit and verifies restoration
into an empty cache.

## Next

Datasets stay anonymous-access for now. Every source added before 1.0 is one
that needs no account or key, so the adapter, transport, cache, and reader
boundaries settle on the simplest cases before a credential layer is shaped
around them; see Later.

Scope one dataset expansion around a concrete analysis use case. These are
candidates to investigate, not selected implementations. Refine a candidate into
an issue with a verified endpoint, bounded example, and acceptance criteria before
moving it to Now. Prefer additions that exercise a useful new access pattern or
reuse an existing one while preserving the adapter, transport, cache/provenance,
and optional-reader boundaries:

- Further NCEI Access Data Service datasets, when a concrete comparison needs them.
- Additional GOES ABI products and sectors, and CO-OPS currents.
- Geospatial readers when a supported dataset and representative fixtures justify them.
- A NEXRAD Level III reader, once the bytes-only adapter has a concrete decoding use case.

## Later

- Sources that need credentials, deliberately after the anonymous surface has
  stopped moving: [EPA AQS as the first probe](https://github.com/jakeryderv/usdata/issues/222),
  which settles where keys live, what provenance records about them, and how
  a manifest stays shareable without one, and then
  [NASA access through earthaccess](https://github.com/jakeryderv/usdata/issues/9).
  The [Census Data API](providers/census.md) belongs here too: it now requires a
  key on every data request, and it is the natural second place-keyed source.
  One such provider is a 1.0 criterion ([versioning](versioning.md)), so this
  is the last workstream before 1.0, not a candidate for the next one.
- [Remote cache backends](https://github.com/jakeryderv/usdata/issues/11):
  a general cache keyed by asset id still needs lookup, freshness, trusted
  upload ownership, and eviction defined. The content-addressed mirror of
  [ADR 0030](adr/0030-content-addressed-mirror.md) answers none of those for
  it and does not preclude it.
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
