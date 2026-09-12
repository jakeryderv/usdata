# Roadmap

## Why

U.S. agencies publish scientific data through different portals, protocols, and
formats. usdata provides shared discovery, acquisition, and provenance so analyses
can declare and preserve their inputs. Scientific transformation and downstream
publishing remain the caller's responsibility.

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

Choose a bounded candidate from Next when its user benefit, scope, exclusions,
and acceptance criteria are ready. The completed
[v0.13.0 first-use review](reviews/first-use-v0.13.0.md) records the published
walkthrough, the changed adapters' live checks, and the new query validation. The
[dataset browser](https://usdata.dev/datasets/) provides search, support and
agency filters, selection rules, and links to examples, including the
[2024 climate comparison](https://usdata.dev/examples/climate-anomalies/).

## Next

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

- Further NCEI Access Data Service datasets, such as hourly normals or Local Climatological Data.
- Bulk directories and archives, such as IBTrACS.
- Additional GOES products/sectors, MRMS, and CO-OPS tides/currents.
- Geospatial readers when a supported dataset and representative fixtures justify them.

## Later

- [NASA access through earthaccess](https://github.com/jakeryderv/usdata/issues/9):
  establish credential ownership and authentication behavior first.
- [Remote cache backends](https://github.com/jakeryderv/usdata/issues/11):
  define lookup, freshness, trusted upload ownership, and eviction while preserving
  checksum, provenance, restoration, and published-file retention contracts.
- GRIB2 model output with cycle/forecast-hour selection, NetCDF CDRs, and static grids.
- Further agencies, live catalog discovery, and third-party registry extensions.
- Format normalization and place-name lookup beyond states and counties.
- A hosted data API or substantial ingestion/analysis jobs when a concrete use
  case requires them. Reassess Railway for a conventional Python/container
  backend at that point; Cloudflare can continue hosting the sites, DNS, and R2.

Deferred issues have no assigned release or date. A registry dataset target of
`later` carries no release commitment; moving a candidate into Now does not
require assigning it a target version.
