# Website operations

The homepage and current documentation are one MkDocs + Material static site at
[usdata.dev](https://usdata.dev/), served by the `usdata-home` Cloudflare Worker.
[ADR 0014](../adr/0014-unified-current-documentation.md) records the scope and archive
policy. Website tooling is not a Python runtime dependency.

## Build and preview

Follow the [development setup](../../README.md#development), then run:

```sh
just check-docs
npm ci --prefix web
npm run check --prefix web
cd web
npx wrangler deploy --dry-run
npx wrangler dev
```

`just docs-serve` previews current content with reload. The local Worker preview
also exercises the frozen archive and redirects. Build the site before running
Worker checks: they use the real static assets, including the search index and
archived docs. No live datasets, R2, or GitHub release downloads are used by builds.
The pinned archive ZIP is already in the repository.

## Automatic deployment

The existing Cloudflare Workers Builds connection to `jakeryderv/usdata` deploys
only main, using these settings:

| Setting | Value |
| --- | --- |
| Worker | `usdata-home` |
| Root directory | `web` |
| Build command | `python3 -m pip install uv==0.12.5 && npm run build && npm run check` |
| Deploy command | `npm run deploy` |
| Production branch | `main` |
| Branch includes | `main` |
| Non-production builds | Disabled |
| Domains | `usdata.dev`, `docs.usdata.dev` |

The build explicitly installs uv because Cloudflare's build image does not
guarantee it is preinstalled. It uses the locked Python docs environment, assembles current content,
checks links and anchors, verifies the archive, then checks Worker types and
runtime behavior. A failed build does not deploy. Repository branch protection
requires full PR CI before merging; Workers Builds runs website validation again
and does not wait for the separate GitHub Actions main run.

Cloudflare's managed build token supplies deployment credentials. No R2 binding,
R2 upload credentials, or separate documentation-publishing workflow is needed.
The Python package release workflow publishes only package artifacts and release
notes. Future package releases do not create new documentation snapshots.

## URLs and the existing archive

- `/` introduces the project; `/start/` is the first-use walkthrough.
- `docs.usdata.dev/` redirects to `usdata.dev/start/`.
- Other paths on the old docs hostname redirect to the same path on `usdata.dev`,
  preserving query parameters and browser fragments.
- `/latest/` redirects to `/start/`; deeper paths under `/latest/` resolve to the
  corresponding current documentation path.
- `/0.10.0/` preserves the frozen published documentation and has a visible archive
  notice. It is not regenerated from current Python code or indexed by current search.
- `/versions.json` is an archive compatibility endpoint, not a list of current
  supported package versions.

`web/archive/README.md` identifies the retained ZIP, original source commits, and
checksum. GitHub release downloads and old R2 snapshots remain retained; the site
no longer reads R2. The retired `usdata` Worker's build trigger is disabled and its
custom domain moves to `usdata-home`. Keep the old deployment available for recovery.

## Verification and recovery

After deployment, check the homepage, start page, navigation, search, API/CLI
references, representative datasets and notebook plots, light/dark modes, and
mobile layout. Check old-host and latest redirects, archive pages/assets, unknown
paths returning 404, and HEAD responses. Inspect the Workers Builds deployment
commit and logs; a local build alone does not prove successful production deployment.

For routine rollback within this architecture, redeploy the prior verified
Worker/assets version, or revert the faulty change through a PR and let main
redeploy. Initial migration rollback additionally requires restoring the old
`docs.usdata.dev` domain association and build settings; prior configuration and
publication procedures remain in Git history. Preserve R2 objects and release
attachments. Never alter the unrelated `jvs-sh` Worker or `pkgs` bucket.
