set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

# Install the toolchain and all dependencies
setup:
    uv sync --all-groups

# Run unit tests
test *args:
    uv run pytest {{args}}

# Run tests that hit live services
test-integration:
    uv run pytest --run-integration -m integration

# Format code in place
fmt:
    uv run ruff format
    uv run ruff check --fix

# Regenerate documentation derived from code and data
docs:
    uv run python scripts/render_registry.py

# Everything CI runs: format check, lint, typecheck, tests, generated docs current
check:
    uv run ruff format --check
    uv run ruff check
    uv run pyright
    uv run pytest --cov=usdata --cov-report=term-missing:skip-covered
    uv run python scripts/render_registry.py --check

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

# Open a release PR: bump version (patch|minor|major), roll CHANGELOG, auto-merge
release bump="minor":
    #!/usr/bin/env bash
    set -euo pipefail
    [ "$(git branch --show-current)" = "main" ] || { echo "run from main"; exit 1; }
    git diff --quiet HEAD || { echo "working tree is not clean"; exit 1; }
    git pull -q --ff-only
    uv version --bump {{bump}} > /dev/null
    v=$(uv version --short)
    uv run python scripts/changelog.py roll "$v"
    uv lock -q
    uv run python scripts/render_registry.py
    git checkout -q -b "release/v$v"
    git commit -qam "chore: release v$v"
    git push -q -u origin "release/v$v"
    gh pr create --title "chore: release v$v" \
        --body "Bumps the version to $v and rolls CHANGELOG. Merging publishes to PyPI and creates the GitHub release."
    gh pr merge --auto --squash
    git checkout -q main
    echo "release PR opened; it merges and publishes when CI passes"
