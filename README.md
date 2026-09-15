# usdata

Discover U.S. scientific datasets, fetch their files, and keep a reproducible
record of where every input came from. One Python SDK and CLI across supported
NOAA and USGS datasets, with provenance sidecars and lockable manifests.

**Pre-alpha.** Features marked **Unreleased** in the documentation require a
source installation; the [changelog](CHANGELOG.md) lists what each published
version contains.

## Documentation

| Site | For |
| --- | --- |
| [usdata.dev](https://usdata.dev/) | What the package is for: the dataset browser and worked examples with saved results |
| [docs.usdata.dev](https://docs.usdata.dev/) | Using the package: install, first dataset, guides, dataset notes, and reference |
| This repository | Changing the project: everything below, plus [contributing](CONTRIBUTING.md), [architecture](docs/architecture.md), [testing](docs/testing.md), [decisions](docs/adr/README.md), [roadmap](docs/roadmap.md), and [versioning](docs/versioning.md) |

```sh
pip install "usdata[pandas]"
usdata search precipitation --location Oklahoma
usdata info noaa:ghcn-daily
```

## Development

Requires a source checkout, [uv](https://docs.astral.sh/uv/), and
[just](https://just.systems/):

```sh
git clone https://github.com/jakeryderv/usdata && cd usdata
just setup     # install toolchain and dependencies
just check     # format, lint, typecheck, offline tests, generated docs, release notices
```

`just setup` uses the tested Python 3.14.7 pin in `.python-version`. Older Linux
uv Python 3.14 builds can crash during NumPy array operations; see
[the upstream fix](https://github.com/astral-sh/python-build-standalone/issues/991).

```sh
just hooks-install # optional: install fast staged-file checks
just test      # all offline tests
just check-pandas  # install the CSV extra and run the same checks
just check-radar   # install the radar extra and run the same checks
just check-netcdf  # install the NetCDF4 extra and run the same checks
just check-grib    # install the GRIB2 extra and run the same checks (Linux, Windows <= 3.13)
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

Offline tests mechanically block network connections. Tests that hit live
services run with `just test-live`; see [testing levels and organization](docs/testing.md).
CI checks Python 3.11 and 3.14 on Linux with core-only, pandas, radar, NetCDF,
and GRIB2 dependency profiles. A further Python 3.11 profile replaces the locked
pandas with the oldest release the project declares, so the `>=` floor is
executed rather than assumed; the number comes from `pyproject.toml` through
`scripts/lowest_version.py`. Installed-wheel checks cover core, pandas, radar,
and NetCDF on Linux, macOS, and Windows. The full offline and live-service
suites run on Linux. `just setup` restores a core-only development environment;
the `check-*` commands install their respective extras.

Releases: `just release minor` prepares a release branch. Update release
notices, then `just release-pr` validates and opens a draft for review. Merging
the reviewed PR publishes to PyPI and creates the tag and GitHub release, then
walks the published package through the getting-started guide. See
[versioning](docs/versioning.md).

The main way the project grows is a new dataset: one registry entry and one
adapter, following [adding a dataset](docs/guides/adding-a-dataset.md). The two
websites deploy automatically from `main`; see
[website operations](docs/guides/website-operations.md) and
[maintaining documentation](docs/guides/documentation.md).

## License

[Apache-2.0](LICENSE).
