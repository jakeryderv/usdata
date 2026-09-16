# 0026: One registry schema, verified against the adapters

Status: accepted. Date: 2026-09-15. Extends [ADR 0001](0001-curated-registry-over-federated-search.md).

## Context

`src/usdata/data/registry.yaml` grew two schemas. The `datasets` block is
loaded into the typed `Dataset` model that the SDK, the CLI, search, and the
manifest validator use. A separate top-level `catalog` block, keyed by dataset
id, holds the fields the documentation and the website need: a short summary,
the delivered formats, the selection rule in one sentence, the required inputs,
the reader extra that opens the files, the provider guide, and the examples that
use the dataset. Only the two generator scripts and the site build read that
block. The SDK cannot see it, so `usdata info` cannot say that GHCN arrives as
CSV and opens with the pandas extra, and nothing stops the two blocks from
disagreeing.

The typed block is also thin. It carries three capability booleans, a license
string, extents, and keywords, and nothing about resolution, update cadence,
latency, citation, terms, or the variables a dataset delivers. Request limits
such as the one-day window on the GLM, MRMS, HRRR, and GFS adapters exist only
as adapter constants and provider prose. The capability booleans are written by
hand and never checked: `usdata info noaa:mrms` advertised spatial and variable
subsetting that the adapter rejects, and a manifest written from that output
failed at pull time.

The first question-first examples ([ADR 0025](0025-examples-as-usage-review.md))
paid for both gaps. A student reads resolution and cadence off provider pages,
learns the window limit from an error, finds MRMS units of `unknown` in the
file, and has no way to ask which extra a dataset needs before installing it.

## Decision

The registry has one schema. Every field the documentation, the website, the
CLI, and the SDK need is a typed, validated field on `Dataset`, and the
`catalog` block is removed. The generators read the model. `usdata info`
prints what the site prints.

The model gains optional metadata fields: `summary`, `formats`, `selection`,
`inputs`, `reader`, `guide`, and `examples` from the old block, plus
`resolution` with `spatial` and `temporal` strings, `update_frequency`,
`latency`, `citation`, `terms`, `variables` as a list of name, units, and
description, and `limits` with `max_window` as an ISO 8601 duration.
Resolution, cadence, and latency are short free text on purpose. Structured
values would cost a schema argument for every dataset and no filter needs them
yet. The `variables` table is structured because it pays twice: it documents
the dataset, and the readers use it to fill `units` and `long_name` where a
file leaves them missing or `unknown`, never overwriting a value the file
provides.

Capabilities and limits are declared in the registry and verified by the
adapter contract tests. A dataset whose entry says it cannot subset spatially
must reject a bbox; an entry's `max_window` must equal the window its adapter
enforces. Declaring in data keeps the registry readable without importing any
adapter, which [ADR 0001](0001-curated-registry-over-federated-search.md) and
the core-never-imports-a-provider boundary require; verifying in tests keeps
the declaration true. `capabilities` gains `partial_fetch`, false everywhere
today, so the GRIB2 index work has a field to flip rather than a schema change.

Entries may name a `system`, the product family or service behind the dataset,
declared in a `systems` table beside `providers` and `domains`. The shared base
classes are already the implementation for those families; the field lets the
documentation and `info` say so.

The lockfile, the provenance sidecar, and the manifest format do not change.

## Consequences

One place to edit per dataset, and one generator input. `usdata info` and a
`datasets` listing can filter and print formats, readers, resolution, cadence,
limits, variables, and citations, which is what the discovery and citation work
builds on. A registry claim that the adapter does not honour fails the offline
test suite instead of a user's pull.

Filling the new fields for the nineteen available datasets is a documentation
task with upstream sources, done once and then maintained per dataset. The
generated catalog pages and the website catalog must be byte-identical across
the fold apart from field order, which the generators' `--check` mode enforces.
Adapters that enforce a window expose the constant so the contract test can
read it.
