# 0021: Publish examples on the main website

Status: Accepted

## Context

Dataset discovery and worked analyses are complementary entry points: users
look for a source or for a question they can answer. An example can use several
datasets, so it needs a single home linked from each relevant dataset. The
maintainer selected a dedicated examples section alongside the dataset browser,
leaving the documentation focused on SDK usage and reference material.

## Decision

Publish the existing examples at `usdata.dev/examples/`, with one canonical page
per folder at `/examples/<example>/`. Keep notebooks, saved outputs, manifests,
and run instructions in the repository's `examples/` directory. Maintain only
the index questions and summaries in `examples/catalog.json`; derive dataset
relationships from the registry's existing `catalog` metadata.

The existing Node website build renders Markdown and saved notebook outputs,
sanitizes HTML, extracts saved plots, and copies exact notebook/manifest downloads.
It never executes a notebook or fetches scientific data. Notebook pages expose
results and expandable code and run instructions; manifest-only pages render the
maintained README. Generated pages exist only in `web/dist/`.

Remove example generation and navigation from MkDocs, and link to the main
website instead. Remove the old disposable `docs/examples/` tree during docs
generation so existing checkouts do not publish duplicate pages. Update source
links once, using canonical website URLs; no build-time URL rewriting or redirect
Worker is introduced. Retired example URLs follow the existing 404 policy.

## Consequences

Examples and datasets share the main website's navigation and visual style.
Examples retain one maintained source and one published page, including when
multiple datasets link to them. The website build validates index membership,
dataset links, saved output types, and local pages/downloads. Website deployment
remains a Node-only static build with no changes to credentials or R2 storage.

This supersedes the example-publishing portion of ADR 0017. Its direct MkDocs
layout and other static-hosting decisions remain in force.
