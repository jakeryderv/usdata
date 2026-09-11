# usdata

Discover U.S. scientific datasets, fetch their files, and keep a reproducible
record of where every input came from. Use the same Python SDK or CLI across
supported NOAA and USGS datasets.

**Pre-alpha.** These docs describe the current source checkout. Features marked
**Unreleased** require a source installation; consult the
[changelog](CHANGELOG.md) for published versions. Other providers are planned.

Project home: [usdata.dev](https://usdata.dev/).
[Documentation and getting started](https://docs.usdata.dev/).

## Start here

```sh
pip install usdata
usdata search precipitation --location Oklahoma
usdata info noaa:ghcn-daily
```

Search uses a curated registry. Fetching contacts the upstream service; readers
open the resulting local files. Provenance and manifests connect those steps.

- [Quick start and documentation](docs/index.md)
- [Fetch and analyze data](docs/guides/fetch-and-analyze.md)
- [Runnable examples with saved outputs](examples/README.md)
- [Readers](docs/reference/readers.md) and [reproducible manifests](docs/reference/manifests.md)

## Source installation

For features marked **Unreleased**, install this checkout with
[uv](https://docs.astral.sh/uv/):

```sh
git clone https://github.com/jakeryderv/usdata && cd usdata
uv sync --extra pandas
uv run usdata info noaa:coops-water-levels
```

Run source examples from this checkout with `uv run usdata` (CLI) or
`uv run python` (Python). The pandas extra enables CSV reading; use `--extra radar`
or `--extra netcdf` for those formats. For contribution checks, continue with
[development setup](#development).

## Providers

Browse the [dataset catalog](docs/generated/catalog/index.md) for current support,
release availability, and dataset details. [Provider access notes](docs/providers/README.md)
explain agency-specific services; the [roadmap](docs/roadmap.md) describes priorities.

## Development

From a [source checkout](#source-installation), requires [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/).

`just setup` uses the tested Python 3.14.7 pin in `.python-version`. Older Linux
uv Python 3.14 builds can crash during NumPy array operations; see
[the upstream fix](https://github.com/astral-sh/python-build-standalone/issues/991).

```sh
just setup     # install toolchain and dependencies
just hooks-install # optional: install fast staged-file checks
just test      # all offline tests
just check     # format, lint, typecheck, offline tests, generated docs, release notices
just check-pandas  # install the CSV extra and run the same checks
just check-radar   # install the radar extra and run the same checks
just check-netcdf  # install the NetCDF4 extra and run the same checks
just notebooks    # launch the optional Jupyter examples environment
just run-notebooks # execute notebooks live in fresh kernels and temporary caches
just docs-serve # build and preview the documentation locally, with reload
just check-docs # validate generated content and build the site strictly
just build     # build wheel and sdist
just smoke     # exercise core and pandas wheel installations outside the checkout
just changes   # preview upcoming release notes
just cleanup 123 # from main: remove PR #123's merged branch and clean worktree
just run search radar
```

Commit hooks fix and format staged Python files using the locked Ruff version,
and check configuration, merge conflicts, and GitHub Actions workflows. Full
validation remains `just check`; `just check-hooks` runs the non-mutating config
and workflow checks alone. Hooks do not rewrite notebooks or raw data fixtures.
The first hook run downloads its isolated tools and requires network access.

Offline tests mechanically block network connections. Tests that hit
live services run with `just test-live`; see [testing levels and organization](docs/testing.md). CI checks Python 3.11 and 3.14 on
Linux with core-only, pandas, radar, and NetCDF dependency profiles. Installed-wheel
checks cover all four profiles on Linux, macOS, and Windows. The full offline and
live-service suites run on Linux. `just setup` restores a core-only development
environment; the `check-pandas`, `check-radar`, and `check-netcdf` commands install
their respective extras.

Releases: `just release minor` prepares a release branch. Update release notices,
then `just release-pr` validates and opens a draft for review. Merging the reviewed
PR publishes to PyPI and creates the tag and GitHub release. See
[docs/versioning.md](docs/versioning.md).

See [provider access notes](docs/providers/README.md),
[docs/architecture.md](docs/architecture.md) for how the pieces fit,
[architecture decisions](docs/adr/README.md) for why, and [CONTRIBUTING.md](CONTRIBUTING.md) to add
a dataset.

## License

[Apache-2.0](LICENSE).
