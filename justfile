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

# Everything CI runs: format check, lint, typecheck, tests
check:
    uv run ruff format --check
    uv run ruff check
    uv run pyright
    uv run pytest

# Build sdist and wheel into dist/
build:
    rm -rf dist
    uv build

# Run the CLI
run *args:
    uv run usdata {{args}}
