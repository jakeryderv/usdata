# Release-note fragments

Each PR adds a small Markdown fragment here. Towncrier builds the changelog at
release time; do not edit `CHANGELOG.md` for pending changes.

From the [development environment](../README.md#development):

```sh
just change +csv-units.fixed.md   # opens the editor; choose a unique slug
just changes                    # preview without writing or consuming files
```

Use `123.added.md` when an issue/PR number is already known, or
`+unique-slug.added.md` otherwise. Write a short sentence describing the change
for users, without a leading bullet. Filenames accept lowercase letters, digits,
and hyphens in slugs. Use ordinary Markdown; avoid relative file links because
the same note appears in the repository, site, and GitHub release.

Types: `breaking`, `security`, `removed`, `added`, `changed`, `fixed`,
`documentation`, or `development`. For a change that needs no public release
note, add an `internal` fragment explaining why; those explanations are checked
but excluded from rendered release notes.

`just check` validates all filenames and nonempty content. PR CI also checks
for a new fragment; release PRs that update the assembled changelog are exempt.
The site builds an upcoming-changes preview directly from these files. Releases
use `just release` and `just release-pr`; see [the release workflow](../docs/versioning.md).
