# 0015: Separate application, documentation, and data storage

Status: Accepted

## Context

The maintainer wants the homepage and future exploration application to evolve
independently of MkDocs, while retaining one current documentation set. Hosted
release-specific docs and their storage recovery machinery are unnecessary at
this early stage. The existing R2 bucket and credentials will support dataset
storage rather than documentation.

## Decision

Serve `usdata.dev` from the `usdata-home` Worker, built from `web/public/` into
ignored `web/dist/`. Serve `docs.usdata.dev` from a separate `usdata-docs` Worker.
MkDocs builds canonical Markdown, Python references, and saved notebooks into
ignored `.build/docs-site/`; `.build/docs/` remains its intermediate staging tree.
Docs-specific branding belongs in `docs/theme/` and deployment code in
`docs/hosting/`. Both sites share visual branding and explicit navigation links.
The existing npm toolchain in `web/` supplies Wrangler and runtime checks for both.

Both sites deploy from main through independent Workers Builds triggers. Each
trigger validates its own build before deployment; full PR CI remains required
before merge. Neither site requires a package release, R2, or a manual publishing
step. Package release behavior is unchanged.

Remove the v0.10.0 archive ZIP, extraction code, and version catalog. Redirect
retired version paths to current documentation; these URLs no longer promise
release-specific content. Use non-cached temporary migration redirects to avoid
adding another persistent redirect layer after the previous hostname reversal.
Existing client-cached permanent redirects may require a cache clear. Preserve
source history and existing GitHub release attachments; do not create new archives.

Retain the `usdata` R2 bucket and its GitHub secrets `R2_ACCESS_KEY_ID` and
`R2_SECRET_ACCESS_KEY`. Remove only the obsolete `docs/` objects after the sites
validate, then remove the retired `usdata` Worker. Connect `data.usdata.dev` for
public reads and configure GET/HEAD CORS for the two production site origins.
Uploads use authenticated S3 access. CORS is a browser policy, not authorization.
Verify the retained credentials through a manually invoked storage check; it
writes and removes only its own temporary object.

R2 is reserved for public dataset files, manifests, provenance, and previews.
Bucket setup alone does not implement remote SDK caching. A registry browser and
one reproducible data example are unscheduled Next candidates. General cache
lookup, freshness, trusted upload ownership, and eviction remain Later work.
Stable published files must not be deleted by future disposable-cache eviction.

## Consequences

The application and documentation can evolve independently, at the cost of two
small deployments. Both are reproducible from the same repository without data
downloads. R2 has a single data-storage purpose. There is no hosted documentation
archive or version index. This supersedes ADR 0014.
