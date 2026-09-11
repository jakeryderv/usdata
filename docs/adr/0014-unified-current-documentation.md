# 0014: One current MkDocs site

Status: Superseded by [ADR 0015](0015-separate-sites-and-data-storage.md)

## Context

The maintainer prefers one integrated website and a familiar MkDocs + Material
experience while usdata is pre-alpha. Maintaining release-specific website
snapshots and a separate publication pipeline adds operational work without a
current need to browse several supported package versions. The existing homepage
and documentation also use independent styling.

## Decision

Build one MkDocs 1.x + Material 9.x static site from main. The landing page, guides,
examples, catalog, and references share navigation, search, and branding. Preserve
canonical Markdown/notebook sources and the generated-catalog ownership boundary.
The website explicitly describes the source checkout; source-only features retain
Unreleased notices. Python packaging and the established package release workflow
stay independent of website publication.

Use the existing `usdata-home` Worker and its managed Workers Builds connection.
Main merges run the strict site build and Worker checks before deployment. Required
PR CI continues to validate the SDK and docs before merge. This automatic website
build does not wait for the separate main-branch GitHub Actions run to complete.
There is no manual docs publication, R2 upload, or package-release prerequisite.
Both domains belong to this Worker; `docs.usdata.dev` redirects to `usdata.dev`.
The `/latest/` alias points to current docs. Current reference paths are preserved.

Freeze the existing v0.10.0 snapshot from the published release ZIP. Commit the
small compressed ZIP and verify its SHA-256 during offline builds. Extract it
under `/0.10.0/` with an archive notice and current-docs link, outside current
navigation and search. Preserve its release downloads and URL suffixes, queries,
and fragments through redirects. The legacy `/versions.json` endpoint reports
only this archive and explicitly marks it archived. Do not create further version
catalogs or archives until there is a concrete need.

Remove superseded publication scripts, workflows, tests, and the boto3 deployment
extra. Retain the old R2 objects and release attachments as historical recovery
material; production serving no longer depends on them. Disable the old docs
Worker's build trigger and detach its custom domain after the new site validates.
Do not delete the old Worker or unrelated Cloudflare resources during migration.

## Consequences

Documentation corrections and new guides appear automatically after main merges.
Readers of a published package must observe Unreleased notices. The website has
one build and one deployment, with a small Worker handling legacy redirects.
A site rollback restores a prior compatible Worker/assets deployment; it does not
require manipulating a storage catalog. Major documentation-tool upgrades require
explicit compatibility review rather than unbounded dependency resolution.

This supersedes ADRs 0012 and 0013. Future multi-version documentation can be
introduced when the project's supported releases and user needs justify it.
