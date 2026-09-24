# Maintaining documentation

MkDocs reads `docs/` directly. Configure navigation, plugins, and the theme in
root `mkdocs.yml`. The theme's header partial is overridden in
`docs/overrides/partials/header.html` to add the Website, Datasets, and Examples
links; it is a copy of the installed mkdocs-material partial with one marked
block added, so re-sync it from `site-packages` whenever the theme is upgraded. A page at `docs/guides/fetch-and-analyze.md` is served at
`https://docs.usdata.dev/guides/fetch-and-analyze/`.

## One audience per host

Each host has one audience and nothing is duplicated between them
([ADR 0023](../adr/0023-one-audience-per-host.md)):

| Host | Audience | Owns |
| --- | --- | --- |
| `usdata.dev` | Someone deciding whether to use the package | Pitch, dataset browser, examples |
| `docs.usdata.dev` | Someone using the package | Install, first dataset, guides, dataset notes, reference |
| GitHub | Someone changing the project | README, contributing, architecture, testing, ADRs, reviews, roadmap, versioning, changelog, site operations |

Contributor and project-record pages live under `docs/` so GitHub renders them
with working relative links, but `exclude_docs` in `mkdocs.yml` keeps them out
of the built site and its search. A user page links to GitHub only for a design
decision that explains behaviour; it never sends a user there for setup or usage.

## Build and preview

From the repository root:

```sh
just docs-build  # generate references, then mkdocs build --strict
just docs-serve  # generate references, then mkdocs serve
just check-docs # also validate committed catalog, release notices, and notebooks
```

The underlying commands use the locked Python docs dependency group:

```sh
UV_PROJECT_ENVIRONMENT=.venv-docs uv run --locked --group docs --no-default-groups python scripts/generate_docs.py
UV_PROJECT_ENVIRONMENT=.venv-docs uv run --locked --group docs --no-default-groups mkdocs build --strict
UV_PROJECT_ENVIRONMENT=.venv-docs uv run --locked --group docs --no-default-groups mkdocs serve
```

MkDocs provides live reload for documentation edits. After changing the registry
or CLI, rerun the generation command. Rebuild the main website after changing
examples; see [website operations](website-operations.md).
There is no custom watcher, source staging tree, link rewriter, or generated
MkDocs configuration. Final HTML lives in ignored `.build/docs-site/`.

## Content ownership

| Content | Edit here |
| --- | --- |
| Install, guides, provider notes, reference pages | Markdown directly under `docs/` |
| Contributor pages (architecture, testing, adding a dataset, this guide, site operations, ADRs, reviews, roadmap, versioning) | Markdown under `docs/`, excluded from the site, read on GitHub |
| Navigation and MkDocs settings | Root `mkdocs.yml` |
| Branding | `docs/assets/` |
| Dataset facts | `src/usdata/data/registry.yaml`; run `just docs` afterward |
| API signatures and descriptions | Python code and docstrings selected by `docs/reference/api.md` |
| CLI reference | Typer app in `src/usdata/cli/` |
| Walkthroughs, studies, and saved plots | `examples/datasets/` and `examples/studies/`, published on `usdata.dev` |
| Study questions and summaries, and the pinned list | `examples/catalog.json` |
| Upcoming changes | Release-note fragments under `changes/` |

`docs/generated/catalog/` is committed generated Markdown. Never add prose to it.
Each dataset has one docs page, its handwritten guide in `docs/providers/`,
which ends with the line that includes its generated reference
(`--8<-- "generated/catalog/<provider>/<name>.md"`); the generated files are
snippets, not pages, and `docs/_redirects` sends their former URLs to the guide
([ADR 0041](../adr/0041-dataset-walkthroughs-and-studies.md)). Each registry
entry records file formats, selection rules, required inputs, the reader extra,
and example sources.

`scripts/generate_docs.py` regenerates only the catalog, CLI reference, and
upcoming changes. It removes the former disposable `docs/examples/` output so
existing checkouts cannot accidentally republish it. A walkthrough is shown on
its dataset's page, `https://usdata.dev/datasets/<provider>/<name>/`, and a
study has its own page, `https://usdata.dev/studies/<slug>/`
([ADR 0041](../adr/0041-dataset-walkthroughs-and-studies.md)).

The main website build reads the saved notebooks, renders their tables and
plots, and copies notebook, manifest, and pinned lockfile downloads beside each
page. No notebook cells execute during a site build, and source outputs,
manifests, and lockfiles stay untouched.

Root README, contribution, security, license, and changelog files stay on
GitHub and are not copied into documentation.

## Examples

Every released dataset has one walkthrough, in
`examples/datasets/<provider>-<name>/`, following the template in
[`examples/README.md`](https://github.com/jakeryderv/usdata/blob/main/examples/README.md#writing-a-walkthrough-or-a-study).
A study is written question-first: its title is the question a student or
analyst would ask, decided before touching the tool, and the notebook answers
it. The same question is the study's entry in `examples/catalog.json`.

Each notebook ends with a short section titled "What was awkward", listing the
places the author had to work around the tool or the data while answering the
question. Every entry there is an issue candidate. This is where usage friction
is recorded, in place of the retired per-release first-use review
([ADR 0025](../adr/0025-examples-as-usage-review.md)); a release should have
exercised its new behavior in at least one example, because the live example run
then guards it.

## Links and validation

Use normal relative Markdown links between docs pages. Links to repository files
outside `docs/` should use their GitHub URLs, or canonical `https://usdata.dev/studies/`
pages for examples. In notebook Markdown, use absolute
`https://docs.usdata.dev/` URLs for documentation and `https://usdata.dev/`
dataset and study URLs for other examples, so links work in both the source
checkout and the website. Same-folder `dataset.yaml` and notebook links are
downloads.

Strict builds check local links and anchors. They do not fetch external links.
Keep Mermaid diagrams in fenced blocks next to their explanation; inspect them
and notebook images in a browser after changes.

See the [example refresh workflow](https://usdata.dev/studies/) for updating saved
outputs, [versioning](../versioning.md) for releases, and
[website operations](website-operations.md) for deployment.
