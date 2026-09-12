# Homepage

`public/` contains the homepage, styling, logo, and 404 page. `build.mjs` copies
these files into disposable `dist/`; Cloudflare serves them directly.

```sh
npm ci
npm run build
npm run check
npm run dev
```

`npm run check` validates asset deployment without publishing.
`npm run deploy` publishes the homepage. No custom Worker script is needed.
Docs content lives in `../docs/`, with configuration in `../mkdocs.yml` and
hosting settings in `../infra/docs.wrangler.jsonc`.
