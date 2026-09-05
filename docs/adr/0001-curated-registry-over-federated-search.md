# 0001: Curated registry over federated search

Status: accepted. Date: 2026-09-04.

## Context

The original vision was unified free-text search across every agency's
catalog. Federated search over agency metadata is what data.gov and science.gov
already do, and results are poor because metadata quality varies wildly between
and within agencies. A query like "tornado radar" only resolves to NEXRAD
Level II because a human knows that mapping.

Search is also the least differentiated part of the idea. The differentiating
part is acquisition, caching, provenance, and reproducible manifests.

## Decision

v0.1 search runs over a curated registry bundled with the package
(`src/usdata/data/registry.yaml`). Each entry names a dataset, its provider,
protocol, extents, server-side subsetting capabilities, and an adapter class.
Ranking is simple keyword matching over id, title, keywords, and description,
filtered by provider, bounding box, and time range.

Live search of agency catalogs (NOAA OneStop, NASA CMR, data.gov) is deferred to
a separate `discover` feature whose purpose is finding candidates to add to the
registry, not serving end-user search.

## Alternatives

- **Federated live search.** Rejected for v0.1: unreliable results, network
  dependency for every search, and no adapter exists for most hits anyway.
- **STAC-only.** Only some sources publish STAC. The registry model is
  STAC-shaped so STAC sources map in cleanly, but STAC is not required.
- **Plugin-discovered registry via entry points.** Deferred. Worth adding once
  third parties want to contribute datasets without upstreaming them.

## Consequences

- Search is fast, offline, and deterministic. Every result is fetchable.
- Coverage is limited to what has been curated. Growth requires adding
  entries and adapters, which is the intended contribution path.
- The registry becomes a maintained artifact: entries must be kept true or
  removed.
