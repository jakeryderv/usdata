# Maintaining documentation

Follow the [development setup](../../README.md#development), then run:

```sh
just docs-serve  # preview at http://127.0.0.1:8000; Ctrl-C stops the server
just docs-build  # strict static build into .build/docs-site/
just check-docs  # check committed generated files, release notices, notebooks, and build
```

The docs commands install the locked `docs` dependency group through uv into
`.venv-docs/`, separate from the active SDK test profile. They do
not require scientific reader extras or live dataset access. Initial dependency
installation needs network access; the content build reads local source and saved
notebook outputs. Documentation checks are part of `just check` and CI's static
job, once per run rather than once per reader profile.

## Edit the source that owns the content

| Content | Maintained source | Generated output |
|---|---|---|
| Project homepage | `web/public/` | Separate site in `web/dist/` |
| First-use walkthrough | `docs/index.md` | Docs home (`index.md`) |
| Overview and development setup | Root `README.md` | Project page (`project.md`) |
| Guides, architecture, provider access notes | Markdown under `docs/` | Site pages |
| Dataset status and capabilities | `src/usdata/data/registry.yaml` | `docs/generated/catalog/` only |
| CLI commands and options | Typer app in `src/usdata/cli/` | CLI reference during the build |
| Public Python signatures and docstrings | `src/usdata/`, selected by `docs/reference/api.md` | API reference during the build |
| Manifest recipes | `examples/*/README.md` and `dataset.yaml` | Example pages and downloadable manifests |
| Examples, plots and provenance snapshots | `examples/*/example.ipynb` | Notebook pages and images during the build |
| Upcoming release notes | `changes/*.md` | Build-only upcoming changes page |
| Published release notes | Towncrier assembles fragments into root `CHANGELOG.md` | Site changelog |

Run `just docs` after changing the registry, and commit its generated Markdown.
These text artifacts keep the catalog usable on GitHub too. README and provider
indexes are handwritten. Never add prose to generated pages.

The registry's `catalog` mapping connects each implemented dataset ID to a unique
handwritten usage guide in `docs/providers/`. The site combines that guide and
its generated catalog reference into one dataset page. Required `summary`,
`formats`, `selection`, `inputs`, `reader_extra`, and `examples` describe the
implemented fetch behavior. Keep file formats and selection explicit: a transport
or capability flag cannot tell readers whether they receive whole files or subsets.
Use `reader_extra: null` when fetching is supported but no bundled reader opens
the format; adding a dataset does not require adding a reader. Links to the guide are
redirected during assembly; GitHub readers use ordinary links between the two
source files. Edit usage and scientific caveats in the guide, and facts in the
registry. The generator checks missing guides, unknown IDs, and obsolete outputs.
The generator does not create provider access notes: add those when introducing
an agency, and link its catalog.

CLI and notebook previews are assembled into ignored `.build/docs/`. MkDocs + Material
renders that tree into ignored `.build/docs-site/`, including API documentation through
`mkdocstrings`. These directories are disposable build outputs. Root files and
examples retain their repository paths in staging, except `docs/index.md` becomes the documentation home (`index.md`),
and the root README becomes `project.md`. The builder adjusts their
relative Markdown links; source links still work on GitHub.
Local links to notebooks become links to rendered pages, with a separate download
link to the original notebook. Notebook cells are never executed during a build.

`just docs-serve` watches the maintained documents, notebooks, Python source,
registry, and generation scripts. It refreshes staged files only when they change;
MkDocs + Material rebuilds the preview. After editing generation scripts, restart the server
so changed Python code is loaded. Run `just docs` before committing registry edits:
the preview renders current data without changing committed generated files.

## Navigation, links, and diagrams

Edit `mkdocs.yml` to change navigation outside the Datasets section. Dataset
navigation is generated from stable IDs and validated catalog metadata into
ignored `.mkdocs.generated.yml`; the empty Datasets section is its insertion point. Organize by reader task, and link
additional provider catalogs and decisions from their indexes. Use relative
Markdown links with explicit filenames so GitHub and the site can resolve them.
Strict builds reject broken internal links and anchors. External URLs are not
probed by this offline gate.

Keep Mermaid source in fenced `mermaid` blocks next to the explanation. Use it
for relationships or sequences that are clearer visually, and check the actual
browser rendering after changing a diagram; a successful Markdown build alone
does not validate Mermaid syntax. Keep critical meaning in the surrounding prose.

For notebook updates, follow the [example refresh workflow](../../examples/README.md).
Saved results describe their recorded executions, not current upstream health.

## Releases and publication

The site currently describes the source checkout. Mark source-only features
**Unreleased** and retain the changelog as the release history. Write user-facing
[release-note fragments](../../changes/README.md); `just release` assembles them
with Towncrier and regenerates registry documentation. The website does not own release policy.

The documentation is a MkDocs + Material site at
[docs.usdata.dev](https://docs.usdata.dev/), separate from the application at
[usdata.dev](https://usdata.dev/). Both build and deploy automatically from main
through Workers Builds. No package release or separate publication command is required.

Edit `docs/theme/assets/usdata.css` for documentation branding. The homepage has
its own source and styles in `web/public/`. Keep their colors, logo, and typography
consistent. The docs environment pins MkDocs 1.x and Material 9.x; major generator
changes require a reviewed migration.

Only current docs are built. Old v0.10.0 and latest URLs redirect to current pages;
there is no archive ZIP or version catalog in the build. Worker previews exercise
these redirects, while `just docs-serve` previews content directly.

See [website operations](website-operations.md) for deployment, redirects, and
recovery. Python distributions remain separate from website assets.
