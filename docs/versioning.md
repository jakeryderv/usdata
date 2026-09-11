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

`just release` requires a clean main checkout, including untracked files. It
updates main, creates `release/vX.Y.Z`, then bumps the version, uses Towncrier to assemble release-note fragments into the
changelog, updates the lockfile, and regenerates registry docs. It reports known
release notices to update. Failures leave the prepared branch/files available for
inspection; nothing is published or merged.

1. Review the version and changelog; change source-only notices to shipped wording
   in maintained docs, navigation, and notebook Markdown. Preserve historical
   notebook code/output snapshots. Run `just docs` if registry metadata changes.
2. Run `just release-pr`. The complete `just check` gate must pass before committing,
   pushing, and opening a **draft** release PR. No auto-merge is enabled.
3. Obtain independent review of the diff and release notes. Commit any corrections,
   rerun `just check`, and push them to the same branch.
4. Mark the reviewed PR ready with `gh pr ready`, then wait with `gh pr checks --watch`.
   Enable squash auto-merge only after review and successful checks:
   `gh pr merge --auto --squash --match-head-commit "$(git rev-parse HEAD)"`.
5. After merge, return to the main checkout and run `just cleanup PR_NUMBER`.
   Verify the publish workflow, GitHub release, and PyPI artifacts.

If preparation stops, inspect `git status` and finish the failed command on the
release branch; use `just release-pr` once version, changelog, lockfile, and docs
are ready. Do not rerun `just release` from that branch or bump again. If a PR
already exists, commit/push corrections normally rather than creating another.
Preparation requires at least one public release-note fragment. Towncrier
consumes fragments when building a dated release entry. Internal-only notes do
not trigger a release; their explanations remain in Git history. If assembly
stops, inspect the changelog and remaining fragments before resuming.

After the PR merges and CI succeeds on that exact main-branch commit, the
`Publish to PyPI` workflow downloads the wheel and sdist from successful CI for
that commit, validates their package name and version, uploads them via trusted
publishing, then creates the `vX.Y.Z` tag and GitHub release with notes from the changelog.

The website follows main and deploys independently of package releases. It does
not create new per-release documentation archives. Existing v0.10.0 downloads
remain on GitHub; old website version paths redirect to current documentation.
Mark source-only features **Unreleased** until their package release. See
[website operations](guides/website-operations.md).

The workflow publishes whatever version `pyproject.toml` declares and tags that
same version, so tag and package can never disagree. Merging a version bump
that is already on PyPI is a no-op.

Every pull request adds a [release-note fragment](../changes/README.md).
`just changes` previews them; the docs site also renders an upcoming-changes page.
The released changelog remains readable on GitHub. Its existing published history
is preserved; new release headings link directly to the corresponding release.

The `pypi` environment accepts only `main`. Manual publishing also requires a
successful main-branch CI run for the selected commit.

CI builds distributions once and smoke-tests the installed wheel outside the
checkout on Linux, macOS, and Windows. Publishing promotes those same files;
it never rebuilds. If the CI artifact has expired, rerun CI for the selected
main commit before retrying publishing. A manual publish selects a successful
main push CI run for the exact commit, subject to the same artifact checks.
The release recipe also regenerates registry docs after changing the version.

`just check` also runs `scripts/check_release_docs.py`. It rejects known versioned
source-only notices and roadmap `Now` headings at or below the declared package
version. On a release PR, update those handwritten notes to shipped wording;
generated registry sections still come from `just docs`. Prefer explicit wording
that names the target minor version for upcoming implemented features so
the check can detect the transition. It scans README, maintained docs, example READMEs, `mkdocs.yml`, and notebook
Markdown cells, excluding historical ADRs, the changelog, code cells, and saved outputs. It does not interpret every
possible phrasing or decide whether future backlog items have shipped.
