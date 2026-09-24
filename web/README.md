# Homepage

`public/` contains the homepage, dataset browser, styling, logo, and 404 page.
`build.mjs` copies these files into disposable `dist/` and renders the examples
there; Cloudflare serves them directly. Colours, fonts, and radii come from
`../docs/assets/tokens.css`, which the docs load too and the build copies to
`/tokens.css`; generated pages share one head, header, and footer from
`layout.mjs`, and `test/layout.test.mjs` keeps the handwritten pages in step.

```sh
npm ci
npm run check
npm run dev
```

`npm run check` builds `dist/` first, then tests catalog search and example
rendering, then validates asset deployment without publishing; the dry run reads
`dist/`, so a clean checkout needs no separate `npm run build`.
`npm run deploy` publishes the homepage. No custom Worker script is needed.
Docs content lives in `../docs/`, with configuration in `../mkdocs.yml` and
hosting settings in `../infra/docs.wrangler.jsonc`.

Pages follow [ADR 0041](../docs/adr/0041-dataset-walkthroughs-and-studies.md):

- `render-datasets.mjs` builds the `/datasets/` grid and one page per
  implemented dataset: preview, at-a-glance facts, a quick start, the
  walkthrough from `../examples/datasets/`, and the studies that use it.
- `render-studies.mjs` builds `/studies/` and one page per study in
  `../examples/studies/`, in the order of `../examples/catalog.json`.
- `notebook.mjs` renders saved notebook outputs; the cell tagged `preview`
  supplies the card and hero image. No data is fetched and no notebook cells
  execute during builds. Downloads preserve source bytes; Markdown and saved
  HTML outputs are sanitized, and saved PNGs are extracted locally.
- `redirects.json` maps each retired `/examples/` URL to its replacement; the
  build writes `_redirects` and refuses a target page that does not exist.

Dataset facts come from the committed index `public/datasets/catalog.json`.
Run `just docs` from the repository root to regenerate it after registry,
example, or package-version changes; `just check-docs` rejects stale output.
The Node-only build needs no Python runtime or upstream access.

The grid is rendered in full at build time; `public/datasets/finder.js` adds
search, agency and topic filters, and the planned toggle, keeping filter state
in the URL. Without script every released dataset is still listed.

The run instructions on `/studies/` come from the `## Run a notebook yourself`
section of `../examples/README.md`. `npm test` checks every page's links and
anchors, downloads, redirects, and output rendering, including rejection of
saved notebook errors.

`public/og.png` is the Open Graph card every page declares, also used by the
README and the GitHub social preview. Its source is `og-card.html`; to
regenerate it, serve this directory and capture the page at 1200 by 630:

```sh
python -m http.server 8765 --bind 127.0.0.1 &
playwright-cli open http://127.0.0.1:8765/og-card.html && playwright-cli resize 1200 630
playwright-cli screenshot --filename=public/og.png && playwright-cli close
```
