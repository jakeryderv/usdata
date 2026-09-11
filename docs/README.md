# Documentation site

This directory owns `docs.usdata.dev`.

- `content/`: maintained pages and committed generated catalog.
- `inputs.yml`: explicit repository files included alongside those pages.
- `build.py` and `mkdocs.yml`: assembly and rendering.
- `theme/`: branding assets.
- `hosting/` and `test/`: Worker, redirects, configuration, and runtime tests.
- `package.json` and `package-lock.json`: independent Node tooling.

From this directory:

```sh
npm ci
npm run build
npm run check
npm run dev
```

Build requires uv; it uses the root project's locked Python docs dependency group.
`npm run serve` previews content with reload; `npm run dev` previews the Worker.
`npm run deploy` publishes this site. The homepage's npm package is not required.
Outputs in `../.build/docs/` and `../.build/docs-site/` are ignored and disposable.

See [maintenance](content/guides/documentation.md) and
[hosting operations](content/guides/website-operations.md).
