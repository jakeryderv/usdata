# 0017: Direct MkDocs and static hosting

Status: Accepted

## Context

The maintainer prefers the conventional MkDocs workflow used by uv. Retaining
old URLs, a separate staging tree, link transformations, and redirect Workers
adds unnecessary machinery to this early project. Old URLs do not need to survive.

## Decision

MkDocs reads publishable content directly from `docs/`, configured by root
`mkdocs.yml`. A focused `scripts/generate_docs.py` command generates catalog and
CLI references, upcoming changes, and saved notebook previews before ordinary
`mkdocs build` or `mkdocs serve`. MkDocs owns live reload. There is no custom
source staging, watcher, navigation/config generation, or link rewriting.

Dataset catalog pages link to handwritten usage guides instead of merging them.
The committed catalog stays under `docs/generated/catalog/`. API references use
mkdocstrings. The ignored `docs/examples/` directory is disposable generated output:
notebook previews, images, downloads, manifests, and standard Markdown includes
of runnable example READMEs. No notebook is executed by documentation generation.

Root README and policy files remain GitHub entry points. Docs and example source
links are updated to their canonical destinations once, rather than transformed
on each build. Current docs URLs follow their file paths without a `/docs/` prefix.
Retired paths return 404; no release archive or compatibility redirects remain.

Keep `usdata.dev`, `docs.usdata.dev`, and R2-backed `data.usdata.dev`. The two
websites deploy automatically as Cloudflare Static Assets with no custom Worker
scripts. Remove their TypeScript type-generation and runtime-test toolchains.
Docs hosting configuration and a pinned Wrangler dependency live under `infra/`;
the homepage stays under `web/`. R2 and its credentials are unaffected.

## Consequences

Content and URL structure correspond directly, and normal MkDocs commands work
after generation. Reference and example source changes require regeneration;
ordinary Markdown edits use MkDocs reload. Old bookmarks may return 404.
This supersedes the layout and URL-preservation decisions in ADR 0016 and the
redirect behavior in ADR 0015. Storage and package-release policies are unchanged.
