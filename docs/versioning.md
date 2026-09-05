# Versioning and Releases

usdata follows [Semantic Versioning](https://semver.org/) with the usual
pre-1.0 reading:

| Bump | Before 1.0 | From 1.0 |
|---|---|---|
| Major | not used | breaking change to the public API |
| Minor | may include breaking changes, called out in the changelog | new functionality, backwards compatible |
| Patch | bug fixes and data updates only, never breaking | same |

## What the public API is

A breaking change is anything that alters documented behavior of:

- The top-level `usdata` package exports listed in `usdata.__all__`, and the
  `usdata.fetch`, `usdata.manifest`, and `usdata.providers.base` modules.
- CLI commands, their flags, output format, and exit codes.
- The manifest and lockfile schemas.
- The provenance sidecar schema.
- Dataset ids in the registry. Removing or renaming one is breaking; adding one
  or updating its metadata is not.

Everything else (internal modules, protocol clients, adapter internals, the
exact contents of bundled data files) may change in any release.

## Path to 1.0

1.0 is tagged when all of these hold:

- Manifest and lockfile formats have not changed for two consecutive minor releases.
- The `Provider` interface has not changed for two consecutive minor releases.
- At least one non-NOAA provider exists, proving the abstraction is not NOAA-shaped.

## Deprecation

From 1.0, anything removed from the public API first emits a
`DeprecationWarning` for at least one minor release. Before 1.0 there is no
deprecation window, but breaking changes are always listed under a
**Breaking** heading in the changelog.

## Cutting a release

Releases are automated from a version bump on `main`. Never hand-write a tag.

```sh
just release minor    # or: patch, major
```

The recipe bumps `pyproject.toml`, rolls the `Unreleased` section of
`CHANGELOG.md` into a dated version heading, opens a release pull request, and
enables auto-merge. After the PR merges and CI succeeds on that exact main-branch commit, the
`Publish to PyPI` workflow builds that commit, uploads it via trusted publishing, then creates
the `vX.Y.Z` tag and GitHub release with notes taken from the changelog.

The workflow publishes whatever version `pyproject.toml` declares and tags that
same version, so tag and package can never disagree. Merging a version bump
that is already on PyPI is a no-op.

Every pull request that changes user-visible behavior adds a line under
`Unreleased` in `CHANGELOG.md`. The release recipe refuses to run if that
section is empty.

The `pypi` environment accepts only `main`. Manual publishing also requires a
successful main-branch CI run for the selected commit.
