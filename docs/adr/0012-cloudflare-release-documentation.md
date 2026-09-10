# 0012: Release documentation in R2, served by a Worker

Status: Accepted for hosting and retention. Publication mechanism superseded by
[ADR 0013](0013-actions-documentation-publication.md).

## Context

The website should default to the latest published package and retain older docs
starting at v0.10.0. The maintainer connects the repository through Cloudflare's
Workers & Pages dashboard and wants Cloudflare to own storage access, without
Cloudflare credentials in GitHub or a deployment branch/hook for each release.

## Decision

Use Workers Static Assets for `usdata.dev`, and a separate Worker at
`docs.usdata.dev` bound to a private `usdata` R2 bucket. Both Worker configurations
live in `web/` and deploy from main through Workers Builds.

GitHub CI builds documentation from exact package and documentation commit IDs.
The normal release workflow promotes those archives alongside the package. A
manual main-only workflow attaches the initial v0.10.0 docs or reviewed corrections
to an existing release; it never changes the package or creates a tag.

Every fifteen minutes, the docs Worker's scheduled handler checks public GitHub
release assets and PyPI. It imports one new or corrected version per invocation,
validates the descriptor and content checksums, and stores files under a prefix
containing the package version and bundle checksum. Only after every write succeeds
does it update `docs/catalog.json` with an R2 conditional write. The catalog selects
the current version and all retained snapshots. Requests never trigger imports.

The importer accepts only stable releases at or above v0.10.0 and no newer than
PyPI's current package version. Archives are bounded to 500 files and 24 MiB of
uncompressed import data; exceeding either limit fails publication visibly until
the implementation and limits are reviewed. No earlier-release backfill is planned.

The current alias and version controls use the uncached catalog. Object cache keys
include the immutable bundle checksum, so a reviewed correction cannot reuse stale
cached bytes. Public version URLs revalidate. Old docs retention is not a package
maintenance promise. No public upload or administrative HTTP endpoint is exposed.

## Consequences

New release content appears after the scheduled import, without a Worker deployment.
Failure leaves the prior catalog available and retries on a later run; incomplete
objects are unreachable through the website. GitHub outages or anonymous API limits
can delay import without taking existing documentation down.

Cloudflare manages build authorization; runtime R2 access uses a binding. GitHub
needs only its normal repository token for release assets and trusted PyPI publishing.
The existing Workers paid plan supports the bounded import workload. Hosting incurs
normal Workers/R2 usage; this decision does not change subscriptions.

Docs and future datasets may share the storage service. This initial implementation
uses only `docs/`; dataset archives, public catalog browsing, and general SDK remote
caching remain separate work. R2 replaces deployment-bundled docs, not the independent
static homepage.
