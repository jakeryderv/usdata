# Maintaining documentation

MkDocs reads `docs/` directly. Configure navigation, plugins, and the theme in
root `mkdocs.yml`. A page at `docs/guides/fetch-and-analyze.md` is served at
`https://docs.usdata.dev/guides/fetch-and-analyze/`.

## Build and preview

From the repository root:

```sh
just docs-build  # generate references/previews, then mkdocs build --strict
just docs-serve  # generate references/previews, then mkdocs serve
just check-docs # also validate committed catalog, release notices, and notebooks
```

The underlying commands use the locked Python docs dependency group:

```sh
UV_PROJECT_ENVIRONMENT=.venv-docs uv run --locked --group docs --no-default-groups python scripts/generate_docs.py
UV_PROJECT_ENVIRONMENT=.venv-docs uv run --locked --group docs --no-default-groups mkdocs build --strict
UV_PROJECT_ENVIRONMENT=.venv-docs uv run --locked --group docs --no-default-groups mkdocs serve
```

MkDocs provides live reload for documentation edits. After changing the registry,
CLI, saved notebooks, or included example instructions, rerun the generation command.
There is no custom watcher, source staging tree, link rewriter, or generated
MkDocs configuration. Final HTML lives in ignored `.build/docs-site/`.

## Content ownership

| Content | Edit here |
| --- | --- |
| Guides, setup, provider notes, reference pages | Markdown directly under `docs/` |
| Navigation and MkDocs settings | Root `mkdocs.yml` |
| Branding | `docs/assets/` |
| Dataset facts | `src/usdata/data/registry.yaml`; run `just docs` afterward |
| API signatures and descriptions | Python code and docstrings selected by `docs/reference/api.md` |
| CLI reference | Typer app in `src/usdata/cli/` |
| Runnable examples and saved plots | `examples/` |
| Upcoming changes | Release-note fragments under `changes/` |

`docs/generated/catalog/` is committed generated Markdown. Never add prose to it.
Dataset reference pages link to handwritten usage guides in `docs/providers/`;
no build step merges the two pages. The registry's `catalog` metadata records
file formats, selection rules, required inputs, reader extras, and example sources.

`scripts/generate_docs.py` regenerates only the catalog, CLI reference, upcoming
changes, and `docs/examples/`. The entire `docs/examples/` tree is ignored and
disposable. It contains notebook Markdown, extracted saved plots, downloadable
notebooks/manifests, and small Markdown include files for example READMEs.
Never put handwritten files there. Notebook cells are not executed by the build,
and source notebooks, outputs, manifests, and lockfiles remain untouched.

Example instructions use the standard `pymdownx.snippets` extension so there is
one maintained README per runnable example. Missing include files fail the build.
Root README, contribution, security, license, and changelog files are linked on
GitHub rather than copied into documentation.

## Links and validation

Use normal relative Markdown links between docs pages. Links to repository files
outside `docs/` should use their GitHub URLs. In example READMEs and notebook
Markdown, link to published docs with absolute `https://docs.usdata.dev/` URLs so
those same instructions work in the source checkout and rendered previews.

Strict builds check local links and anchors. They do not fetch external links.
Keep Mermaid diagrams in fenced blocks next to their explanation; inspect them
and notebook images in a browser after changes.

See the [example refresh workflow](../examples/README.md) for updating saved
outputs, [versioning](../versioning.md) for releases, and
[website operations](website-operations.md) for deployment.
