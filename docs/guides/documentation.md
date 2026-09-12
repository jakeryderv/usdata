# Maintaining documentation

MkDocs reads `docs/` directly. Configure navigation, plugins, and the theme in
root `mkdocs.yml`. A page at `docs/guides/fetch-and-analyze.md` is served at
`https://docs.usdata.dev/guides/fetch-and-analyze/`.

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
| Guides, setup, provider notes, reference pages | Markdown directly under `docs/` |
| Navigation and MkDocs settings | Root `mkdocs.yml` |
| Branding | `docs/assets/` |
| Dataset facts | `src/usdata/data/registry.yaml`; run `just docs` afterward |
| API signatures and descriptions | Python code and docstrings selected by `docs/reference/api.md` |
| CLI reference | Typer app in `src/usdata/cli/` |
| Runnable examples and saved plots | `examples/`, published on `usdata.dev/examples/` |
| Example index questions and summaries | `examples/catalog.json` |
| Upcoming changes | Release-note fragments under `changes/` |

`docs/generated/catalog/` is committed generated Markdown. Never add prose to it.
Dataset reference pages link to handwritten usage guides in `docs/providers/`;
no build step merges the two pages. The registry's `catalog` metadata records
file formats, selection rules, required inputs, reader extras, and example sources.

`scripts/generate_docs.py` regenerates only the catalog, CLI reference, and
upcoming changes. It removes the former disposable `docs/examples/` output so
existing checkouts cannot accidentally republish it. All examples now have one
canonical page at `https://usdata.dev/examples/<example>/`.

The main website build reads the maintained example READMEs and saved notebooks,
renders their tables and plots, and copies notebook and manifest downloads into
`web/dist/examples/`. Notebook pages include the README as expandable run
instructions; manifest-only pages show it directly. No notebook cells execute
during a site build, and source outputs, manifests, and lockfiles stay untouched.

Root README, contribution, security, license, and changelog files are linked on
GitHub rather than copied into documentation.

## Links and validation

Use normal relative Markdown links between docs pages. Links to repository files
outside `docs/` should use their GitHub URLs, or canonical `https://usdata.dev/examples/`
pages for examples. In example READMEs and notebook Markdown, use absolute
`https://docs.usdata.dev/` URLs for documentation and `https://usdata.dev/examples/`
URLs for other example pages so links work in both the source checkout and the
website. Same-folder `dataset.yaml` and `example.ipynb` links are downloads.

Strict builds check local links and anchors. They do not fetch external links.
Keep Mermaid diagrams in fenced blocks next to their explanation; inspect them
and notebook images in a browser after changes.

See the [example refresh workflow](https://usdata.dev/examples/) for updating saved
outputs, [versioning](../versioning.md) for releases, and
[website operations](website-operations.md) for deployment.
