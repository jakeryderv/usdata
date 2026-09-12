# Website and data storage operations

The homepage, documentation, and dataset files have separate responsibilities.
[ADR 0017](../adr/0017-direct-mkdocs-and-static-hosting.md) records the direct
MkDocs and static hosting setup.

| Address | Source | Output | Cloudflare resource |
| --- | --- | --- | --- |
| `usdata.dev` | `web/public/` | `web/dist/` | `usdata-home` Static Assets |
| `docs.usdata.dev` | `docs/`, root `mkdocs.yml` | `.build/docs-site/` | `usdata-docs` Static Assets |
| `data.usdata.dev` | Published dataset/cache objects | Uploaded objects | `usdata` R2 bucket |

The two sites have no custom Worker scripts. Cloudflare serves their static
assets and 404 pages directly. Neither website reads R2 or packages HTML in the
Python distribution. Documentation generation uses the Python docs dependency
group; `infra/` contains only its pinned Wrangler deployment tooling and config.
The homepage has its own Node build and deployment commands in `web/`.

## Build and preview

```sh
just docs-build
just docs-serve
npm ci --prefix infra
npm run dev:docs --prefix infra
npm ci --prefix web
npm run build --prefix web
npm run dev --prefix web
```

MkDocs serves on port 8000, the docs asset preview on 8788, and the homepage
preview on 8787. Site cross-links use production hostnames. Preview each local
site directly when checking an unmerged change.

For deployment dry runs, use `npm run check:docs --prefix infra` and
`npm run check --prefix web`. These validate static asset packaging without
publishing. No TypeScript types or Worker runtime tests are needed.

## Automatic deployment

Two Workers Builds triggers connect to `jakeryderv/usdata`, include only `main`,
and watch all repository paths. The homepage uses root `web`, builds with
`npm run build && npm run check`, and deploys with `npm run deploy`.

The docs trigger uses the repository root. Its build command is:

```sh
python3 -m pip install uv==0.12.5 && UV_PROJECT_ENVIRONMENT=.venv-docs uv run --locked --group docs --no-default-groups python scripts/generate_docs.py && UV_PROJECT_ENVIRONMENT=.venv-docs uv run --locked --group docs --no-default-groups mkdocs build --strict && npm ci --prefix infra && npm run check:docs --prefix infra
```

Its deploy command is `npm run deploy:docs --prefix infra`, using
`infra/docs.wrangler.jsonc`. Deployment credentials are Cloudflare's managed build
token; neither site receives the R2 credentials. PR CI validates both builds and
the SDK before merge. Site deployment remains independent of package releases.

## Public URLs

Current docs use `/guides/`, `/reference/`, `/generated/catalog/`, and `/examples/`
paths directly. Root repository policies and the changelog link to GitHub.
Obsolete `/docs/`, `/start/`, `/latest/`, `/0.10.0/`, version indexes, and copied
policy URLs return 404. Former docs paths on the homepage also return 404.
There are no compatibility redirects or archived docs objects.

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

Check the homepage links, docs search, catalog-to-guide links, API/CLI references,
notebook plots/downloads, and the expected 404 responses at retired URLs.
Confirm automatic builds ran from the merged commit. Use the separate R2 storage
check only when changing the data-storage setup.

Roll back through a reviewed repository revert and rebuild both sites. Old
Worker versions may contain obsolete redirect behavior; prefer rebuilding the
intended source. Website deployments do not alter dataset objects or credentials.
