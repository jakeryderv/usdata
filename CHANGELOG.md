# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) as described in
[docs/versioning.md](docs/versioning.md).

## [Unreleased]

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

[Unreleased]: https://github.com/jakeryderv/usdata/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/jakeryderv/usdata/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/jakeryderv/usdata/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/jakeryderv/usdata/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/jakeryderv/usdata/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jakeryderv/usdata/releases/tag/v0.1.0
