# AGENTS.md

Context for coding agents working in this repo. Setup and commands are in
[README.md](README.md); do not duplicate them here.

## What this is

A Python SDK + CLI (`usdata`) giving one interface to U.S. public scientific
data, with provenance and reproducible manifests. Read
[docs/architecture.md](docs/architecture.md) before touching more than one module.

## Layout

- `src/usdata/models.py`: all shared pydantic types. Change here ripples everywhere.
- `src/usdata/data/registry.yaml`: the curated dataset catalog. Adding a dataset = a YAML entry + an adapter class.
- `src/usdata/providers/<agency>/`: one `Provider` subclass per dataset.
- `src/usdata/protocols/`: transport only (`http`, `s3`). No dataset knowledge here.
- `scripts/`: generators for bundled data files. Regenerate, don't hand-edit `data/*.csv`.
- `src/usdata/cli/app.py`: Typer app. Keep it thin; logic lives in the library.
- `tests/unit/`: fast, offline. `tests/integration/` (when present): live services, marked `integration`.
- `docs/adr/`: decisions already made. Read before proposing to reverse one.

## Constraints

- Core must not import any provider module; use `load_adapter`.
- Providers must not write to the cache or provenance; they return assets and fetch bytes to a given path.
- Core runtime deps are pydantic, pyyaml, typer. Anything heavier goes behind an extra.
- Unit tests must not touch the network. Mock HTTP; mark live tests `integration`.
- Every registry entry must be true: real id, real endpoint, correct capabilities.

## Workflow

- `just check` must pass before a PR. It runs ruff format check, ruff lint, pyright, pytest.
- Conventional commits (`feat:`, `fix:`, `docs:`, ...). No Co-Authored-By trailers.
- Trunk-based: short branch → PR → squash merge to main. `main` is protected; never push to it directly.
- User-visible changes add a line under `Unreleased` in `CHANGELOG.md` in the same PR.
- Releases: `just release <bump>`. Never create tags or GitHub releases by hand. See `docs/versioning.md`.
- A design choice that gets argued about becomes an ADR in `docs/adr/`.
