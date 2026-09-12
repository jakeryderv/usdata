# Homepage

`public/` contains the homepage, dataset browser, styling, logo, and 404 page. `build.mjs` copies
these files into disposable `dist/`; Cloudflare serves them directly.

```sh
npm ci
npm run build
npm run check
npm run dev
```

`npm run check` tests catalog search and validates asset deployment without publishing.
`npm run deploy` publishes the homepage. No custom Worker script is needed.
Docs content lives in `../docs/`, with configuration in `../mkdocs.yml` and
hosting settings in `../infra/docs.wrangler.jsonc`.

The browser at `/datasets/` searches a committed static metadata index in
`public/datasets/catalog.json`. Run `just docs` from the repository root to
regenerate it after registry, catalog metadata, or package-version changes.
`just check-docs` rejects stale output. The generator reuses the documentation
catalog's availability rules and validates the same guide/example sources.
The Node-only homepage build needs no Python runtime or upstream access.

Search matches dataset IDs, topics, descriptions, formats, and selection rules;
agency and support filters combine with it. Ready-to-use entries are the default;
planned entries explicitly cannot fetch data. Filter state stays in the URL.
If JavaScript or catalog loading fails, a link opens the documentation catalog.
