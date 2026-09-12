# Infrastructure

- `r2-data.json`: dataset bucket domain and browser read policy.
- `docs.wrangler.jsonc`: static docs deployment to `docs.usdata.dev`.
- `package.json` and lockfile: pinned Wrangler deployment CLI.

Build docs from the repository root with `just docs-build`, then:

```sh
npm ci --prefix infra
npm run check:docs --prefix infra
npm run dev:docs --prefix infra
```

`npm run deploy:docs --prefix infra` publishes the built assets.
See [website operations](../docs/guides/website-operations.md).
