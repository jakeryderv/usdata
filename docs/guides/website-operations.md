# Website operations

The homepage and documentation use separate Cloudflare Workers from `web/`.
[ADR 0012](../adr/0012-cloudflare-release-documentation.md) records storage and
release ownership; [ADR 0013](../adr/0013-actions-documentation-publication.md)
records direct Actions publication. The Python package does not depend on website
tooling.

The sites are published at [usdata.dev](https://usdata.dev/) and
[docs.usdata.dev](https://docs.usdata.dev/). Publication began with v0.10.0;
`/versions.json` on the documentation host reports the current catalog. The
[publication issue](https://github.com/jakeryderv/usdata/issues/56) records the
initial deployed source revisions and verification evidence.

## Connect and deploy

Install Node.js 22 or newer, then `npm ci --prefix web`. Run
`npm run check --prefix web`; this generates binding types and runs TypeScript and
offline workerd tests. From `web/`, run `npx wrangler deploy --dry-run` and
`npx wrangler deploy --config wrangler.home.jsonc --dry-run` before deployment.
The pinned workerd override keeps the test pool on the same runtime as Wrangler;
the sharp override supplies the patched development dependency. Review both when
updating tooling.

Create a private Standard R2 bucket named `usdata` in the account managing
`usdata.dev`. Do not enable a public R2 URL. The docs Worker accesses only `docs/`
through its `DOCS` binding; no dataset objects are managed here.

Connect `jakeryderv/usdata` through Workers & Pages, with production branch `main`:

| Setting | Documentation | Homepage |
| --- | --- | --- |
| Worker name | `usdata` | `usdata-home` |
| Root directory | `web` | `web` |
| Build command | `npm run check` | `npm run check` |
| Deploy command | `npm run deploy` | `npm run deploy:home` |
| Production domain | `docs.usdata.dev` | `usdata.dev` |

Use Cloudflare's managed build token. Disable non-production branch builds initially;
PR CI provides isolated runtime tests. Production R2 must not receive writes from
unreviewed branches. Custom domains are configured after preview verification.
Worker code uses the native R2 binding; Workers Builds manages deployment
authorization. GitHub Actions publishes docs using a separate R2 Account API token
with Object Read & Write scoped to the `usdata` bucket. Store its credentials as
repository Actions secrets `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` using
`gh secret set NAME` (interactive hidden input); no `.env` or general Cloudflare
API token is needed.

The production account is `d4e3fe7d69a3ac8f446d4c3de2ca051b`; the `usdata.dev`
zone is `12c05b7627e36c9f2ca88ce04ccb8647`. Both Workers share the repository
connection and existing `usdata-workers-builds` managed token. Their independent
build triggers deploy only `main`. Custom domains are declared in the respective
Wrangler configurations so future deployments preserve them. The stable
`usdata.jakervanslyke.workers.dev` and `usdata-home.jakervanslyke.workers.dev`
addresses remain available for deployment checks; per-version preview URLs are
disabled. Do not change the unrelated `jvs-sh` Worker or `pkgs` bucket.

## Documentation publishing

Regular package releases attach the validated `release-documentation` CI artifact
from the exact successful main commit. It contains a portable ZIP, an import bundle,
and a JSON descriptor with version, package/docs commit IDs, file count, and digest.
The shared `docs-publish.yml` workflow downloads the exact descriptor and bundle
from a public stable GitHub release using GitHub authentication, confirms the
package exists on PyPI, validates every file, uploads the snapshot, then updates
the catalog conditionally. Normal releases and docs corrections invoke it.

To publish the initial v0.10.0 docs or a reviewed correction, merge the documentation
changes, wait for successful main CI, then run:

```sh
gh workflow run docs-release.yml -f version=0.10.0
```

This workflow uses the chosen version's tagged `src/` tree, the main commit's docs
and locked documentation tooling, and a temporary checkout. It builds strict links
and references; it never runs notebooks live. The descriptor is attached after both
archives. The package remains unchanged. Inspect the built archive before publishing
corrections whose guides may mention newer features; only references are mechanically
pinned to the old package. Normal releases continue to use `just release`.

The docs Worker serves requests only; there is no polling or scheduled import.
Publication completes in the Actions workflow without redeploying the Worker.
`/versions.json` shows the current version and available versions. `/` and `/latest/` redirect to
the current package's docs. A selector appears when two versions are available;
missing pages during a switch return to the chosen version's start page with a notice.

CI's documentation artifacts remain temporary. GitHub release attachments and R2
snapshots provide persistent retention from v0.10.0 onward. Unreleased main changes
do not advance the current docs version.

## Verification and logs

Check both preview and canonical domains: HTTPS, root/latest redirects, navigation,
search, API/CLI references, all released dataset pages, notebooks and manifest
links, Mermaid diagrams, 404 responses, and version switching. Test two versions
using isolated fixtures, never synthetic releases on the public site.

GitHub Actions records archive validation, upload, and catalog promotion results.
Workers Logs records serving errors as `docs-request-failed` events. The Workers
Builds dashboard records deployed source commits and build output. `npx wrangler tail` from `web/` also streams runtime logs.
A successful site deploy does not prove that a release archive has been published;
verify `/versions.json` and actual documentation pages separately.

## Recovery

A failed upload leaves the catalog unchanged. Inspect the Actions failure, resolve
credential or artifact problems, then rerun the failed job. To retry the exact
archived bytes independently, run the main-only publisher with the full docs commit
from that release's descriptor:

```sh
gh workflow run docs-publish.yml -f version=0.10.0 -f docs_commit=FULL_DOCS_COMMIT
```

This also supports a deliberate content rollback by selecting a previously verified
archived docs commit for the same version. Save the existing `docs/catalog.json`
before a rollback and record the restored revision. A same-version rollback changes
the active docs revision; it does not move the current package version backward.
Review any newer queued publication before restoring an older revision. Repeating
the active revision is a no-op; old snapshots are retained. A conditional catalog
conflict fails without overwriting the winning publication: inspect that revision
before retrying. Never delete old objects as part of rollback.

For Worker code, redeploy a previously verified configuration/code revision through
Workers Builds. Code rollback does not roll back R2 contents. Record the restored
source revision and catalog separately.
