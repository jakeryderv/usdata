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
and [changelog](../CHANGELOG.md) for completed work. Current validation results
belong in [CI](https://github.com/jakeryderv/usdata/actions/workflows/ci.yml) and
[live checks](https://github.com/jakeryderv/usdata/actions/workflows/integration.yml).

## Now

Make the existing workflows easy to learn and reproduce before choosing the next
dataset expansion:

- [Publish the home page and versioned documentation (#56)](https://github.com/jakeryderv/usdata/issues/56):
  use Cloudflare Workers Static Assets for a small project home at `usdata.dev`
  and independently deployed documentation at `docs.usdata.dev`. The home page
  introduces the project, installation, and links, leaving room for later additions.

The docs entry point opens the latest published package's documentation. Preserve
versioned builds at paths such as `docs.usdata.dev/0.10.0/`, with a version selector
and a notice on older versions. Generate API, CLI, and dataset references from the
corresponding release; do not substitute unreleased code from main. Allow reviewed
documentation-only corrections for a release, recording the documentation revision
while keeping references tied to that package version.

Automate publication from validated builds and retain release documentation beyond
temporary CI artifact retention. Archive versions going forward; backfill older
versions only when useful. Resolve deployment credentials and the build/archive
workflow before connecting the custom domains. Detailed setup and completion
criteria belong in #56; selecting this design does not mean the sites are live.

The completed [v0.10.0 first-use review](reviews/first-use-v0.10.0.md) provides
the verified workflow baseline and corrected examples for publication.

## Next

After publication, investigate these bounded website additions before selecting
implementation work:

- A searchable dataset browser generated from the curated registry, showing
  support, formats, selection rules, and examples. It can start with a static
  metadata index and does not require mirroring upstream datasets.
- An R2 archive of the exact inputs used by selected release examples. Record
  dataset IDs, queries/source assets, retrieval times, upstream revisions where
  available, checksums, and provenance. Manifests link releases or examples to
  those snapshots; the package version alone does not identify data bytes. Reuse
  identical objects across releases instead of duplicating their contents.

These are candidates without deadlines or release assignments. The archive is
separate from general SDK remote caching in #11 and from mirroring entire sources.

Scope one dataset expansion around a concrete analysis use case. These are
candidates to investigate, not selected implementations. Refine a candidate into
an issue with a verified endpoint, bounded example, and acceptance criteria before
moving it to Now. Prefer additions that exercise a useful new access pattern or
reuse an existing one while preserving the adapter, transport, cache/provenance,
and optional-reader boundaries:

- Further NCEI Access Data Service datasets, such as climate normals.
- Bulk directories and archives, such as HURDAT2 and IBTrACS.
- Additional GOES products/sectors, MRMS, and CO-OPS tides/currents.
- Geospatial readers when a supported dataset and representative fixtures justify them.

## Later

- [NASA access through earthaccess](https://github.com/jakeryderv/usdata/issues/9):
  establish credential ownership and authentication behavior first.
- [Remote cache backends](https://github.com/jakeryderv/usdata/issues/11):
  preserve checksum, provenance, and restoration contracts.
- GRIB2 model output with cycle/forecast-hour selection, NetCDF CDRs, and static grids.
- Further agencies, live catalog discovery, and third-party registry extensions.
- Format normalization and place-name lookup beyond states and counties.
- A hosted data API or substantial ingestion/analysis jobs when a concrete use
  case requires them. Reassess Railway for a conventional Python/container
  backend at that point; Cloudflare can continue hosting the sites, DNS, and R2.

Deferred issues have no assigned release or date. A registry dataset target of
`later` carries no release commitment; moving a candidate into Now does not
require assigning it a target version.
