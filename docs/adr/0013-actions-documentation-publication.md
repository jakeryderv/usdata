# 0013: Publish documentation directly from GitHub Actions

Status: Accepted

## Context

[ADR 0012](0012-cloudflare-release-documentation.md) used a scheduled importer to
avoid Cloudflare credentials in GitHub. The maintainer now accepts a bucket-scoped
R2 credential in GitHub Actions. Polling adds publication delay, repeated discovery
requests, and a second release orchestrator. A production import also encountered
a GitHub API 403; existing documentation stayed available.

## Decision

GitHub Actions owns documentation publication. After publishing the package and
attaching the validated CI archives to its GitHub release, the release workflow
calls a shared publisher. Reviewed docs-only corrections use the same publisher.
An explicit main-only workflow can retry or restore an existing archive without
rebuilding it, modifying a package, or creating a release.

The publisher downloads the exact descriptor and bundle with GitHub's repository
token, confirms the stable package exists on PyPI, and verifies the version, tagged
package commit, reviewed docs commit, archive checksum, safe unique paths, file
checksums, and completeness before writing anything. Existing bounds remain:
v0.10.0 onward, 500 files, and 24 MiB compressed and expanded data. Files go under
`docs/<version>/<bundle-sha256>/`; every upload carries a transport checksum. Only
after all uploads succeed does an ETag-conditional write promote `docs/catalog.json`.
Other versions and old snapshots remain available. The highest published version
with a complete snapshot is current; uploading an older version's correction does
not move current backward. A catalog conflict fails visibly for operator review.

Use an R2 Account API token with Object Read & Write scoped only to the `usdata`
bucket. Store its Access Key ID and Secret Access Key as repository Actions secrets
`R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY`. The endpoint and bucket name are
non-secret configuration. No `.env`, general Cloudflare API token, webhook,
publication branch, public R2 endpoint, or administrative HTTP handler is needed.

The docs Worker only serves the catalog and objects through its native R2 binding.
Remove its scheduled handler and cron trigger. Workers Builds continues deploying
homepage and serving code from main using its separate managed build token.
The domains, URL layout, release ZIP attachments, source pinning, correction policy,
and future dataset scope from ADR 0012 remain in effect.

## Consequences

Publication happens in the release workflow instead of waiting for a timer, and
failures appear in that workflow's logs. Partial uploads never become live. Retrying
an already active revision is a no-op. Restore content by explicitly publishing a
previously verified archived docs commit; retained snapshots are never deleted.
Worker deployment and content publication remain independent.

The maintainer must retain and rotate the bucket-scoped Actions credentials.
Normal serving no longer calls GitHub or PyPI and requires no credential secrets.
The Python SDK gains no runtime dependency; boto3 belongs to deployment tooling.
