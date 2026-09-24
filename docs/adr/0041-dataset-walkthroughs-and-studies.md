# 0041: Every dataset has a walkthrough and its own page; examples that answer a question are studies

Status: accepted. Date: 2026-09-24. Updates
[ADR 0025](0025-examples-as-usage-review.md) and
[ADR 0029](0029-committed-example-lockfiles.md), and applies
[ADR 0023](0023-one-audience-per-host.md).

## Context

`examples/` holds 32 folders that do two different jobs. Twenty-two teach one
dataset: how to select it, what arrives, how to open it, and what surprised the
author. Ten answer a question, most of them by joining several datasets, such
as the severe-weather case study or the storm surge at Cedar Key. The website
lists all 32 as one grid with the same card, labelled by format ("Notebook ·
saved results", "Manifest walkthrough") rather than by what they are for.
Twelve of the single-dataset folders have a manifest and a README but no
notebook, so their cards have no picture, and six released datasets appear only
inside a multi-dataset example or nowhere with an example of their own.

A dataset's story is split across three pages on two hosts: an entry in the
website's dataset list, a generated reference page in the docs, and a
handwritten guide in the docs. The website list is text only; there is no page
a person can land on that says what one dataset is, shows it, and shows how to
use it.

The [path to 1.0](../versioning.md#path-to-10) asks that every dataset have a
worked example. The current layout cannot say whether that is true without
reading every README.

## Decision

### Two kinds of example

A **walkthrough** teaches one released dataset. There is exactly one per
dataset, in `examples/datasets/<provider>-<name>/`, holding a notebook named
after the folder, its `dataset.yaml`, and a committed lockfile when pinned. It
uses only that dataset and follows one template, as markdown headings in this
order:

1. The dataset's title and a short paragraph: what it is, who publishes it, and
   what one file holds.
2. `Select`: the manifest and what its query means.
3. `What arrives`: the pull, the files, their sizes, and their provenance.
4. `Open`: the reader and the columns or variables that matter.
5. `A first look`: one figure, the dataset's preview, and a sentence reading it.
6. `Pin and cite`: `verify` and `cite`.
7. `What was awkward`: the friction list ADR 0025 asks for.

A **study** answers a question, usually by joining datasets, in
`examples/studies/<slug>/`, holding a notebook named after the folder and its
`dataset.yaml`. Its title is the question, as ADR 0025 requires. It opens with
a `Data` section naming its sources, may organize its analysis freely, and ends
with `Pin and cite` and `What was awkward`.

In both, the notebook is the whole document: the run instructions, the
findings, and the friction list move out of the folder README into the
notebook, and the folder has no README. `examples/README.md` remains the index
for GitHub readers and holds the shared setup instructions.

Every notebook's first code cell sets the shared figure style inline, so a
downloaded notebook needs nothing from the repository. Exactly one code cell is
tagged `preview`, and its output is exactly one PNG. That image is the card and
hero image for the dataset or study on the website. Previews are real figures
drawn from real data; there are no stock photographs or illustrations.

### Index and relationships

`examples/catalog.json` lists the studies in display order, each with its slug,
title, and one-sentence summary, and separately lists the example folders whose
lockfiles are committed. Walkthroughs need no entry: the folder name is the
dataset ID, and the title and summary come from the registry.

Each registry entry's `examples` lists its walkthrough first and then every
study that uses the dataset. The generator checks both directions: a
released dataset's walkthrough folder is listed, and every dataset a study's
manifest names lists that study.

### The website

- `usdata.dev/datasets/` is a grid of cards, one per released dataset: preview
  image, title, agency, topic, formats, and a badge when a key is required.
  Search and agency and topic filters narrow it; with no search it groups by
  topic. Planned datasets are behind a toggle and have no page.
- `usdata.dev/datasets/<provider>/<name>/` is one page per released dataset:
  preview, short description, an at-a-glance strip (coverage, resolution,
  cadence, formats, credentials), a quick start for the CLI, Python, and a
  manifest, the walkthrough rendered inline, the studies that use the dataset,
  and links to its reference in the docs.
- `usdata.dev/studies/` and `usdata.dev/studies/<slug>/` replace
  `/examples/`. Each study page shows its datasets as links to their pages.
- Every `/examples/` URL redirects permanently to the dataset or study page
  that replaced it.
- Both hosts use the same navigation (Datasets, Studies, Docs, GitHub) and one
  set of colour, type, and spacing tokens, kept in `docs/assets/tokens.css` and
  copied into the website at build time.

The at-a-glance strip summarizes the registry entry and links to the docs for
the rest. It is the one piece of dataset reference that appears on both hosts,
because a person deciding whether to use a dataset needs it before they read
reference documentation (ADR 0023).

### The docs

Each dataset has one docs page: its handwritten guide, followed by the
generated reference (parameters, variables, catalog facts). The separate
generated per-dataset pages and the docs' own dataset list are removed, their
URLs redirect, and the docs' dataset section links to the website's grid.

## Consequences

Whether every dataset has a worked example becomes a file check: the build
fails when a released dataset has no walkthrough folder, a notebook has no
preview, or a study's manifest and the registry disagree. That check turns on
once the missing notebooks exist; until then a walkthrough folder without a
notebook renders its README and its card shows a topic tile.

Twenty-seven walkthroughs and eleven studies are more notebooks to run weekly
than 32 examples were, and each needs live data to refresh. They are written
one dataset per pull request against the template, so a reviewer compares one
notebook with the template rather than with its neighbours.

Folder moves change repository paths in the registry, the notebook runner's
targets, the Integration inventory, and the lockfile whitelist, and change
every `/examples/` link. The redirects keep published links working; repository
paths change once.

The single-dataset examples that already answered a question (the goes
mesoscale sector's evolution, the wildfire-smoke fortnight) stay studies, and
their datasets also get walkthroughs, so one dataset can appear in both.
