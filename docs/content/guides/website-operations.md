# Website and data storage operations

The application, documentation, and dataset files have separate responsibilities.
[ADR 0015](../adr/0015-separate-sites-and-data-storage.md) records the decision.

| Address | Source | Build output | Cloudflare resource |
| --- | --- | --- | --- |
| `usdata.dev` | `web/public/`, `web/src/` | `web/dist/` | `usdata-home` Worker + Static Assets |
| `docs.usdata.dev` | `docs/content/`, generated references, `docs/inputs.yml` | `.build/docs-site/` | `usdata-docs` Worker + Static Assets |
| `data.usdata.dev` | Future published datasets/cache objects | Uploaded objects | `usdata` R2 bucket |

Both build outputs are ignored and disposable. `.build/docs/` is intermediate
MkDocs staging. `site/` was the previous combined build output and is no longer
used. Neither website reads R2 or packages its HTML in the Python wheel.
Documentation styles and hosting configuration live in `docs/theme/` and
`docs/hosting/`. Each site owns its npm package, lockfile, checks, and deployment
commands. See [ADR 0016](../adr/0016-site-source-boundaries.md).

## Build and preview

Follow the [development setup](../project.md#development), then run:

```sh
just check-docs
npm ci --prefix web
npm run build --prefix web
npm run check --prefix web
npm ci --prefix docs
npm run check --prefix docs
```

Preview the homepage with `npm run dev --prefix web` (port 8787), and documentation
with `npm run dev --prefix docs` (port 8788). The Worker previews exercise
redirects. Links between sites use the production hostnames; inspect each local
preview directly when validating an unmerged change. `just docs-serve` previews
current documentation with reload on port 8000. Builds do not execute notebooks,
fetch scientific data, or require R2 credentials.

## Automatic deployment

Two Workers Builds triggers connect to `jakeryderv/usdata` and include only
`main`. Each runs from its own site directory. All repository paths trigger a
build, so changes to Python signatures, examples, docs, or shared tooling cannot
leave stale output.

| Worker | Root | Build command | Deploy command |
| --- | --- | --- | --- |
| `usdata-home` | `web` | `npm run build && npm run check` | `npm run deploy` |
| `usdata-docs` | `docs` | `python3 -m pip install uv==0.12.5 && npm run build && npm run check` | `npm run deploy` |

The docs build explicitly bootstraps uv, then uses the locked Python environment.
Each site deploys only after its own checks pass. Required PR CI validates both
sites and the SDK before merge; Workers Builds does not wait for a separate main
GitHub Actions run. Cloudflare's managed build token deploys the Workers. R2
credentials are not passed to either site build. Package releases remain independent.

For a dry run, use `npm run deploy --prefix web -- --dry-run` or
`npm run deploy --prefix docs -- --dry-run`.

## Compatibility URLs

Former documentation paths on `usdata.dev` redirect to `docs.usdata.dev`.
The docs Worker maps `/start/`, `/latest/`, and `/0.10.0/` to current docs. Deeper
latest/version paths preserve their suffixes. Query strings and browser fragments
survive redirects. These URLs no longer select release-specific documentation.
Former contribution, security, license, and release-fragment instruction pages
redirect to their canonical GitHub files. There is no hosted archive or `versions.json`; missing paths return 404.

Migration redirects use 302 with `Cache-Control: no-store`. A browser that cached
the earlier permanent docs-to-home redirects may need its site cache cleared.
Existing GitHub release attachments and Git history remain historical records;
they are not downloaded by site builds. The retired `usdata` Worker and R2 `docs/`
objects are removed after successful cutover.

## R2 dataset storage

`infra/r2-data.json` records the intended bucket domain and CORS configuration.
`data.usdata.dev` exposes objects for public reads, with GET/HEAD CORS for
`https://usdata.dev` and `https://docs.usdata.dev`. CORS does not restrict access
outside browsers. All objects placed in this bucket must be suitable for public
access. No browser receives upload credentials. Keep the managed `r2.dev` endpoint
disabled; the custom domain is the public interface.

GitHub retains `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY`. Authenticated uploads
use the account's R2 S3 endpoint and require Object Read & Write access to `usdata`.
Do not rotate or remove these credentials merely because the former docs workflow
is gone. Reassess their scope when a future uploader needs different access.

Run the manual **Check R2 data storage** GitHub Actions workflow from main to
verify the stored credentials, an authenticated upload/download, public delivery,
and CORS. It uses a unique `checks/github-<run>-<attempt>.txt` object and always
attempts to delete that exact object. It does not upload any dataset or alter
other objects. A failed cleanup must be resolved using the key shown in the run.

The bucket is ready for data; SDK remote caching is not implemented. Before a
first dataset upload, define stable object identities, provenance, checksums,
upload ownership, and retention. Published example inputs must survive disposable
cache eviction. The [roadmap](../roadmap.md) keeps exploration in Next and general
remote caching in Later without dates or release commitments.

## Verification and recovery

Verify both custom domains, homepage links, docs navigation/search, references,
notebook plots, mobile layout, legacy redirects, and 404/HEAD behavior. Check each
Workers Builds run against the merged commit. Verify R2 using the manual workflow.

For a site rollback, redeploy a compatible Worker/assets version or revert through
a PR. A site rollback does not restore deleted R2 objects. Versions from before
this split may contain incompatible domain routing; avoid rolling back only one
side of that migration. Do not restore a dependency on the retired R2 docs objects.
Unrelated Cloudflare resources are outside this setup.
