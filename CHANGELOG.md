# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) as described in
[docs/versioning.md](docs/versioning.md).

## [Unreleased]

### Added

- Datasets carry a `status` (available, stub, planned). `search` and `info` show it; fetching a
  planned dataset exits 3 with a clear message.
- Planned registry entries for USGS, NASA, EPA, FEMA, Census, USDA, and GOES so the roadmap is
  visible from `usdata search` and the docs.
- Provider metadata (name, homepage) in the registry; README gains a generated per-provider table.
- Datasets carry a `domain` (shared taxonomy across providers), `since` (version shipped) or
  `target` (planned phase or `later`). `search` and `info` show them; the roadmap lists
  datasets by target version, generated from the registry.

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

[Unreleased]: https://github.com/jakeryderv/usdata/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/jakeryderv/usdata/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/jakeryderv/usdata/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jakeryderv/usdata/releases/tag/v0.1.0
