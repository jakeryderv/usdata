set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

# Install the core development toolchain
setup:
    uv sync --group dev

# Install fast checks for staged files (optional, once per clone)
hooks-install:
    uv run --locked pre-commit install

# Validate repository config and workflows without rewriting files
check-hooks:
    uv run --locked pre-commit run --all-files --hook-stage manual

# Run all offline tests (pass pytest selectors as arguments)
[positional-arguments]
test *args:
    uv run pytest "$@"

# Run tests that hit live services
[positional-arguments]
test-live *args:
    uv run pytest --run-live -m live "$@"

# Compatibility alias for existing callers
test-integration: test-live

# Format code in place
fmt:
    uv run ruff check --fix
    uv run ruff format

# Regenerate documentation derived from code and data
docs:
    uv run python scripts/render_registry.py

# Preview the documentation locally, watching maintained sources
docs-serve:
    UV_NO_SYNC=0 UV_PROJECT_ENVIRONMENT=.venv-docs uv run --group docs --no-default-groups python scripts/docs_site.py serve

# Build static documentation without publishing
docs-build:
    UV_NO_SYNC=0 UV_PROJECT_ENVIRONMENT=.venv-docs uv run --group docs --no-default-groups python scripts/docs_site.py build

# Check documentation ownership, saved outputs, links and anchors
check-docs:
    uv run python scripts/render_registry.py --check
    uv run python scripts/check_release_docs.py
    just check-notebooks
    just docs-build

# Regenerate Census state/county boxes (downloads source archives unless --source-dir is set)
places *args:
    uv run python scripts/build_places.py {{args}}

# Complete offline pre-PR gate, also used in separate CI jobs
check: check-static check-tests

# Repository-wide checks that do not vary across dependency profiles
check-static:
    uv lock --check
    uv run ruff format --check
    uv run ruff check
    just check-hooks
    uv run python scripts/check_changes.py
    just check-docs

# Type and behavior checks for the active dependency profile
[positional-arguments]
check-tests *args:
    uv run pyright
    uv run pytest --cov=usdata --cov-branch --cov-report=term-missing:skip-covered "$@"

# Run the full checks with optional CSV readers installed
check-pandas:
    uv sync --group dev --extra pandas
    UV_NO_SYNC=1 just check

# Run the full checks with the optional NEXRAD reader installed
check-radar:
    uv sync --group dev --extra radar
    UV_NO_SYNC=1 just check

# Open the interactive examples in JupyterLab
notebooks:
    uv run --group examples --extra radar --extra netcdf jupyter lab examples

# Validate committed notebook structure and saved outputs without fetching data
check-notebooks:
    uv run python scripts/check_notebooks.py

# Execute all notebooks against live services; --write refreshes committed outputs
[positional-arguments]
run-notebooks *args:
    uv run --group examples --extra radar --extra netcdf python scripts/run_notebooks.py "$@"

# Run checks with the optional NetCDF4 reader installed
check-netcdf:
    uv sync --group dev --extra netcdf
    UV_NO_SYNC=1 just check

# Build sdist and wheel into dist/
build:
    rm -rf dist
    uv build

# Install the built wheel in isolation and check SDK, CLI, and bundled resources
smoke:
    uv run --no-project python scripts/smoke_wheel.py

# Run the CLI
run *args:
    uv run usdata {{args}}

# Preview pending release notes without changing files
changes:
    uv run python scripts/check_changes.py --preview

# Create a release note; for example: just change +csv-units.fixed.md
[positional-arguments]
change name:
    uv run towncrier create "$1"

# Prepare a release branch; edit release notices before opening the PR
release bump="minor":
    uv run python scripts/release.py prepare {{bump}}

# Validate prepared release changes and open a draft PR (no auto-merge)
release-pr:
    uv run python scripts/release.py pr

# From main, remove only a merged PR's unchanged local branch and clean worktree
cleanup pr:
    uv run python scripts/cleanup_pr.py {{pr}}
