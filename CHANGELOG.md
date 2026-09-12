# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) as described in
[docs/content/versioning.md](docs/versioning.md).

## [Unreleased]

Upcoming notes are maintained as [individual fragments](changes/README.md).
The documentation site assembles their preview automatically.

<!-- towncrier release notes start -->

## [0.13.0](https://github.com/jakeryderv/usdata/releases/tag/v0.13.0) - 2026-09-12


### Added

- Add a searchable dataset browser at https://usdata.dev/datasets/ with agency and support filters, download selection rules, required inputs, example links, and copyable inspection commands. Extend the climate-anomalies notebook with a calculated summary of warmer months and annual precipitation relative to the station normals.

### Changed

- GOES queries span at most 7 days and NEXRAD queries at most 31 days, rejected before any request instead of listing hour by hour or day by day without bound. USGS daily-value listing now probes one row per page instead of downloading every JSON page, so dry runs and manifest resolution no longer transfer the data twice.
- Move all twelve worked examples to https://usdata.dev/examples/ with a question-based index, source-dataset links, saved results, expandable notebook code, and exact notebook/manifest downloads. Keep their maintained sources in the repository's examples directory and update dataset and documentation links to the single published copy.

### Fixed

- Adapters now share one query-validation step, so every dataset rejects free text, unsupported location, variable, or date filters, and conflicting selectors the same way instead of some ignoring them. This fixes a crash when CoastWatch received timezone-naive datetimes from the SDK, GHCN-Daily silently preferring `stations` over a `location`, and NEXRAD, USGS, and CoastWatch ignoring `text` or `variables`.

## [0.12.0](https://github.com/jakeryderv/usdata/releases/tag/v0.12.0) - 2026-09-12


### Added

- Added `noaa:hurdat2`, the NHC HURDAT2 best-track database, with a `basin` parameter, whole-file revision selection, and a local reader that parses the fixed-format text into one pandas row per track point.
- `usdata info <dataset>` now lists the provider-specific `--param` keys each adapter accepts, with a one-line description each, and the generated catalog pages show the same table.

### Changed

- The optional CSV reader now accepts pandas 2.2 or newer instead of requiring pandas 3.0, so `usdata[pandas]` installs alongside existing pandas 2 environments.

### Documentation

- Add a runnable climate-anomalies notebook that compares a year of NOAA GSOM monthly observations against the 1991-2020 station normals, and document which NCEI normals data types `units=metric` converts correctly, including the uncorrected `MLY-TAVG-NORMAL` and the mis-converted diurnal-range and standard-deviation codes.

### Development

- CI now runs the offline suite against the oldest pandas the project declares, so the supported floor is tested rather than assumed.

## [0.11.0](https://github.com/jakeryderv/usdata/releases/tag/v0.11.0) - 2026-09-12


### Added

- Add `noaa:climate-normals`: 1991-2020 monthly, daily, or annual/seasonal station normals from the NCEI Access Data Service, selected with a `period` parameter, optional month-day windows, and station discovery.
- Add the project homepage at https://usdata.dev and current documentation at https://docs.usdata.dev, with separate automatic static-site deployments from main.
- Restoring a lockfile now reports every asset whose upstream bytes changed in one run and leaves the lockfile untouched; `usdata pull --update <asset or dataset id>` (or `pull(update=[...])`) accepts the new bytes and rewrites only those pins.

### Fixed

- Reject reserved query names passed through fetch --param with a clear input error and the appropriate dedicated flag, instead of crashing or bypassing provider-parameter validation.
- Treat timezone-free timestamps in direct NEXRAD SDK queries as UTC, matching build_query and the CLI regardless of the machine timezone.

### Documentation

- Build documentation directly from `docs/` with standard MkDocs commands and
  serve both websites as static assets. Remove custom staging, link rewriting,
  Worker scripts, and obsolete URL redirects. Documentation now uses clean
  `/guides/`, `/reference/`, and `/examples/` paths; retired URLs return 404.
- Define Now, Next, and Later planning by scope and readiness, with bounded acceptance criteria and no deadlines or promised releases.
- Fix GSOY and CO-OPS Python manifest examples to use pathlib.Path, support running them from a published installation, and demonstrate fresh-cache restoration in the first-use walkthrough.
- Reserve R2 at https://data.usdata.dev for dataset storage, with a manual credential, public-access, and CORS check. SDK remote caching remains future work.

### Development

- Check both hosting toolchains for weekly npm dependency updates, and point package homepage and documentation metadata to the public sites. Consolidate pending website notes around the current deployment setup.

## [0.10.0](https://github.com/jakeryderv/usdata/releases/tag/v0.10.0) - 2026-09-09


### Added

- CO-OPS observed water levels for one station, explicit datum and UTC interval, with raw CSV quality fields, response validation, and a reproducible manifest example.
- `noaa:gsoy` annual station CSVs with complete UTC year selection, shared NCEI geographic discovery, reproducible restoration, and a small manifest example.

### Documentation

- Keep generated catalog files separate from handwritten documentation and combine dataset reference facts with usage guides in the local docs site.
- Make the dataset catalog easier to browse with Released, Source only, and Planned labels; explicit file formats and selection behavior; and automatic dataset navigation.
- Make the first-use walkthrough the site home, separate NOAA dataset guides from service research, and clarify source installation and reproducibility.

### Development

- Add optional fast commit hooks, workflow linting, and PR-title validation; pin GitHub Actions to reviewed commits while retaining Dependabot updates.
- Allow focused manual live-test and notebook CI runs while retaining complete weekly coverage; summarize test failures, skips, and timings in Actions.
- Assemble release notes with Towncrier fragments, validate notes in PRs, and preview upcoming changes in the documentation.
- Generate the radar-site CSV with LF line endings so fresh worktrees stay clean, and apply lint fixes before formatting.
- Prepare releases on a branch before editing files, validate draft release PRs before review/merge, check navigation and notebook release notices, and provide guarded cleanup for merged local branches and worktrees.

## [0.9.0] - 2026-09-09

### Documentation

- Default the documentation site to dark mode, with a light-mode toggle.

- Add a local documentation site with navigation, Mermaid diagrams, generated API/CLI references, saved notebook previews, and strict CI link checks. Separate generated dataset catalogs from provider access notes.

### Added

- Per-dataset live checks, independent example jobs, retained test/coverage and
  failed-notebook diagnostics, and scheduled minimum-core-dependency validation.

- Shared adapter conformance scenarios for every available dataset, covering
  deterministic listing, fetch destinations, byte preservation, and client ownership.

- Documented L0–L4 test levels, responsibility-based suites, and `just test-live`
  selection; existing integration command and marker aliases remain supported.

- Pure `select_by_time` asset selection with explicit tolerance and nearest/prior
  direction, signed offsets, candidate counts, and an explicit no-match result.
- Explicit zero-based radar sweep selection with `FetchedAsset.open(sweep=...)`
  and an executed Storm Events / NEXRAD / GOES event-context notebook.

### Fixed

- Require Typer 0.18 or newer; the old declared minimum failed to construct the
  CLI with modern union annotations and lacked current Click compatibility.

- Reject truncated S3 listings with missing or cycling continuation tokens instead
  of returning incomplete assets or requesting pages indefinitely.

- Reject NEXRAD decoder tables that misalign moment and coordinate records,
  including equal-length sweeps following a missing interior end marker; valid
  explicitly selected sweeps remain readable without silently dropping others.
- Reject out-of-range or non-finite point coordinates and negative/non-finite
  radii before bounding-box clipping; complete the manifest provider options for
  GSOM, GOES ABI, and Storm Events.

## [0.8.0] - 2026-09-09

### Added

- Optional local NetCDF4 opening with eager xarray loading, CF decoding,
  closed file resources, source metadata, and an executed GOES infrared notebook.
- `noaa:goes-abi` CONUS Cloud and Moisture Imagery with explicit satellite/channel
  selection, precise scan times and sizes, and checksum-verified NetCDF downloads.
- Storm Events annual event-details gzip CSVs, selecting current creation-date
  revisions with exact source-byte provenance and locked restoration; local
  compressed CSV opening preserves event and geographic identifier strings.
- Executed Storm Events notebook with local Oklahoma/date filters, event-record
  and damage-rating plots, and source/reporting caveats.
- Optional NEXRAD Level II opening with xradar sweep DataTrees, native units and
  flag masking, source provenance, and an executed reflectivity notebook.

### Changed

- Replace example analysis scripts with executed Jupyter notebooks containing
  compact data previews, plots, and source provenance. Add an optional examples
  environment, offline notebook checks, and isolated live execution/refresh commands.
- Pin the development interpreter to Python 3.14.7 to avoid an upstream crash
  affecting NetCDF decoding in older Linux uv Python builds.

## [0.7.0] - 2026-09-08

### Added

- Opt-in GHCN station-search diagnostics with bounded response details, and
  independent live checks for geographic discovery and explicit-station downloads.
- `noaa:gsom` monthly station CSVs through NCEI, with geographic discovery,
  complete-month selection, reproducible restoration, and a pandas analysis example.
- Terminal progress for CLI fetch and pull, showing known asset sizes, HTTP download
  bytes and retry attempts, and validated cache hits. Disable with `--no-progress`;
  redirected output retains its existing format.

## [0.6.0] - 2026-09-08

### Added

- Optional `FetchedAsset.open()` CSV reading through `usdata[pandas]`, including
  ERDDAP units metadata, string identifiers/codes, explicit dtype/date/column/row
  options, and a fetch-to-analysis example. Opening leaves raw bytes and provenance intact.

### Changed

- Test core-only and pandas installations in CI and installed-wheel checks.
- Check versioned source-only documentation notices during validation so release
  PRs cannot carry known stale availability wording.
- Focus v0.6 on optional CSV readers and practical usage; NASA, model output,
  climate grids, and remote caching remain follow-up work.

## [0.5.0] - 2026-09-05

### Breaking

- Manifest pulls now fail when a required source resolves to no assets. Set
  `allow_empty: true` per source to permit an intentionally empty result.
- `verify` rejects a manifest edited since locking (exit 2), matching `pull`.
- NOAA adapters reject unknown provider parameters, empty explicit identifiers,
  invalid units, and conflicting or invalid radar selectors.

### Fixed

- Generated provider and roadmap docs distinguish unreleased implementations
  from support included in the declared package version.
- GET metadata and download requests retry transient failures up to three attempts,
  respecting bounded `Retry-After` delays and preserving existing files on failure.
- Release publishing promotes the distributions from successful CI for the exact
  release commit, with version checks, instead of rebuilding.

### Changed

- Narrow v0.5 to USGS, ERDDAP/CoastWatch, complete place lookup, and reliability;
  additional NOAA adapters and optional readers remain follow-up work.
- Enforce offline unit tests and smoke-test the installed wheel on Linux, macOS,
  and Windows. Add release-tool regression tests.
- Add a manifest reference and a small NOAA/USGS example with a live round-trip test.

### Added

- `noaa:coastwatch-sst`: bounded ERDDAP gridded CSV subsets by location, UTC
  time, and variable, with optional spatial stride and reproducible restoration.
- Census 2025 lookup for 56 states/DC/territories and 3,235 counties/equivalents,
  including county/state names and quoted FIPS. Add `--location` as an alias for
  `--state`. Generated bounds replace the six approximate seed boxes, so
  geographic queries may select different stations; existing lockfiles stay pinned.

- `usgs:water-daily`: the first non-NOAA adapter, using the modern USGS Water Data
  API for paginated CSV downloads by site or bbox, dates, parameter codes, and
  statistic. Preserves units and quality metadata; supports cached fetches,
  manifest pull, locked restoration, and verification without new dependencies.

## [0.4.0] - 2026-09-05

### Breaking

- Manifest and source fields reject unknown keys instead of silently ignoring them;
  provider-specific inputs remain supported under `params`.

### Fixed

- Verify cached bytes and source provenance before reuse or fresh lockfile creation.
- Reject unsafe cache paths, including symlinks escaping the cache root.
- Preserve existing files after failed downloads or checksum mismatches; replace downloads,
  provenance, and lockfiles atomically using unique temporary files.
- Reuse provider clients across downloads and close internally owned clients on success or failure.
- Report invalid dates, radar IDs, manifest YAML, and lockfiles with clear CLI input errors.
- Infer multiple domains correctly when constructing a custom registry without a domain catalog.
- Gate package publishing on successful CI for the exact main-branch release commit.

## [0.3.0] - 2026-09-05

### Added

- `usdata pull` fetches every source in a manifest and writes a lockfile pinning each asset's
  checksum and provenance; a later `pull` restores from the lockfile without re-resolving, and
  refuses (until `--force`) if the manifest changed. `usdata verify` reports missing or altered
  cached files. Python API: `usdata.pull`, `usdata.verify`.
- Datasets carry a `status` (available, stub, planned). `search` and `info` show it; fetching a
  planned dataset exits 3 with a clear message.
- Planned registry entries for USGS, NASA, EPA, FEMA, Census, USDA, and GOES so the roadmap is
  visible from `usdata search` and the docs.
- Provider metadata (name, homepage) in the registry; README gains a generated per-provider table.
- Datasets carry a `domain` (shared taxonomy across providers), `since` (version shipped) or
  `target` (planned phase or `later`). `search` and `info` show them; the roadmap lists
  datasets by target version, generated from the registry.

- 26 NOAA registry entries spanning 18 domains, each verified for anonymous access
  (except GHCN-Hourly, whose entry says its bulk path is unconfirmed), with target phases.
  The NOAA provider page gains a data-landscape table mapping domains to entries.

### Changed

- `usdata search` hides planned datasets unless `--planned` is given.

### Changed

- Dataset reference moved to `docs/providers/`: one page per provider with hand-written access notes and a generated dataset table, plus a generated index.

## [0.2.1] - 2026-09-05

### Added

- Type information is shipped (`py.typed`).
- Contributor docs: `CONTRIBUTING.md`, `SECURITY.md`, a guide to adding datasets, issue and PR templates.

## [0.2.0] - 2026-09-05

First usable release.

### Added

- Curated dataset registry with keyword search filtered by provider, bounding box, and time.
- `noaa:ghcn-daily` adapter: station observations via the NCEI search and data services.
- `noaa:nexrad-level2` adapter: Level II volume scans from the `unidata-nexrad-level2` bucket over anonymous S3.
- Local cache with sha256 verification and a provenance sidecar for every fetched file.
- CLI: `usdata search`, `info`, `fetch` (with `--dry-run`), and manifest validation in `pull`.

## [0.1.0] - 2026-09-05

- Placeholder release reserving the package name. No functionality.

[Unreleased]: https://github.com/jakeryderv/usdata/tree/main/changes
[0.9.0]: https://github.com/jakeryderv/usdata/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/jakeryderv/usdata/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/jakeryderv/usdata/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/jakeryderv/usdata/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/jakeryderv/usdata/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/jakeryderv/usdata/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/jakeryderv/usdata/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/jakeryderv/usdata/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/jakeryderv/usdata/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jakeryderv/usdata/releases/tag/v0.1.0
