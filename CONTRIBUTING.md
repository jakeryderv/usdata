# Contributing

Thanks for helping make U.S. public data easier to use. This file is the
contributor's onboarding page: setup, the commands, what CI checks, the
workflow, and how releases happen. Read [architecture](docs/architecture.md)
before touching more than one module, and [AGENTS.md](AGENTS.md) if you are
working with a coding agent.

## Setup

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
`just setup` restores a core-only development environment; the `check-*`
commands below install their respective extras.

## Commands

```sh
just hooks-install # optional: install fast staged-file checks
just test          # all offline tests
just check-pandas  # install the CSV extra and run the same checks
just check-radar   # install the radar extra and run the same checks
just check-netcdf  # install the NetCDF4 extra and run the same checks
just check-grib    # install the GRIB2 extra and run the same checks (Linux, Windows <= 3.13)
just notebooks     # launch the optional Jupyter examples environment
just run-notebooks # execute notebooks live in fresh kernels and temporary caches
just docs-serve    # build and preview the documentation locally, with reload
just check-docs    # validate generated content and build the site strictly
just build         # build wheel and sdist
just smoke         # exercise core and pandas wheel installations outside the checkout
just changes       # preview upcoming release notes
just cleanup 123   # from main: remove PR #123's merged branch and clean worktree
just run search radar
```

Commit hooks fix and format staged Python files using the locked Ruff version,
and check configuration, merge conflicts, and GitHub Actions workflows. Full
validation remains `just check`; `just check-hooks` runs the non-mutating config
and workflow checks alone. Hooks do not rewrite notebooks or raw data fixtures.
The first hook run downloads its isolated tools and requires network access.

## What CI checks

Offline tests mechanically block network connections. Tests that hit live
services run with `just test-live`; see [testing levels and organization](docs/testing.md).
CI checks Python 3.11 and 3.14 on Linux with core-only, pandas, radar, NetCDF,
and GRIB2 dependency profiles. A further Python 3.11 profile replaces the locked
pandas with the oldest release the project declares, so the `>=` floor is
executed rather than assumed; the number comes from `pyproject.toml` through
`scripts/lowest_version.py`. Installed-wheel checks cover core, pandas, radar,
and NetCDF on Linux, macOS, and Windows. The full offline and live-service
suites run on Linux, and the worked examples run live on a schedule.

## Workflow

1. Open or pick an issue. Dataset requests use the "Dataset request" template.
2. Branch from `main` with a type prefix: `feat/`, `fix/`, `docs/`, `refactor/`, `chore/`.
3. Make the change. Add or update tests. Run `just check`.
4. Add a [release-note fragment](changes/README.md); use `internal` with a reason when there is no user-facing change.
5. Open a pull request. The template has the checklist. CI must pass; `main`
   only accepts squash merges, so the PR title becomes the commit message and
   should be a [Conventional Commit](https://www.conventionalcommits.org/):
   `feat: add usgs:nwis-daily adapter`. CI validates this title, including edits.

Fast commit hooks are optional; see [Commands](#commands). CI runs the
same configuration and workflow checks even when hooks are not installed.
Dependabot proposes weekly updates to the SHA-pinned GitHub Actions. To refresh
hook revisions, run `uv run pre-commit autoupdate` and review them in a PR.

## After merging

Return to the main checkout (`git switch main` when working in the primary
checkout), then run `just cleanup PR_NUMBER`. Cleanup verifies that the PR merged
into main and that the local branch still matches its exact head. It removes a
clean associated topic worktree and the local branch, then leaves main current.
It refuses dirty worktrees, changed branch tips, and fork PRs. Ignored lockfiles,
downloads, and notebook reports must be preserved elsewhere first; only known
regenerable tool/build caches are disposable. GitHub deletes the
remote branch after merge. Keep any branch with additional work for a separate PR.

## Adding a dataset

This is the main way the project grows. The full walkthrough is in
[docs/guides/adding-a-dataset.md](docs/guides/adding-a-dataset.md). In short:

- one entry in `src/usdata/data/registry.yaml`,
- one `Provider` subclass under `src/usdata/providers/<agency>/`,
- adapter tests with mocked HTTP under `tests/adapters/`,
- one live test under `tests/live/` marked `live`.

## Conventions

- Python 3.11+. Formatting and linting by ruff, types by pyright, both enforced in CI.
- Core runtime dependencies stay at pydantic, pyyaml, typer, httpx. Anything
  heavier goes behind an optional extra.
- Offline tests never touch the network. Live tests are marked `live` and
  run weekly, not on PRs.
- Bundled data files under `src/usdata/data/` are generated by scripts in
  `scripts/`. Regenerate rather than hand-edit.
- Design decisions that get argued about become an ADR in `docs/adr/`.
- Commit messages have no `Co-Authored-By` trailers.

## Releases

`just release minor` prepares a release branch. Update release notices, then
`just release-pr` validates and opens a draft for review. Merging the reviewed
PR publishes to PyPI and creates the tag and GitHub release, then walks the
published package through the getting-started guide. See
[versioning](docs/versioning.md). The two websites deploy automatically from
`main`; see [website operations](docs/guides/website-operations.md) and
[maintaining documentation](docs/guides/documentation.md).

## Definition of done

- Acceptance criteria in the issue are met.
- Tests added or updated; `just check` passes.
- Docs updated: README, guides, registry entry, or ADR as appropriate.
- Release-note fragment added; generated changelog history is not edited by hand.
- Security implications considered (see [SECURITY.md](SECURITY.md)).

For documentation changes, see [maintaining the docs](docs/guides/documentation.md).
