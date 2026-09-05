# 0005: Generated Census place envelopes from KML

Status: accepted. Date: 2026-09-05.

## Context

Six hand-written state rectangles do not provide consistent national coverage.
State and county lookup should work offline without a heavy GIS dependency.
The Census Bureau publishes nationwide generalized boundaries as zipped KML,
which the standard library can parse, as well as shapefiles requiring additional
geometry tooling. Existing queries use a single non-wrapping `BBox`.

## Decision

Generate compact state/county CSV rows from the 2025 1:500,000 KML archives.
Retain FIPS, names, state qualifiers, and min/max bounds over all polygon vertices.
Bundle a source manifest with hashes, counts, and vintage. Preserve the current
`BBox` contract: antimeridian-spanning regions use a conservative broad envelope
rather than silently dropping island polygons. Explain this limitation in the
[place reference](../reference/places.md).

Resolve states first, then qualified county names, with explicit ambiguity
errors and quoted FIPS as an unambiguous alternative. Regeneration remains a
maintainer operation; runtime and unit tests need no source downloads.

## Consequences

The package gains full state/county coverage with no new dependencies. Generated
bounds can change station selection relative to the seed rectangles. Envelopes
are approximate spatial filters, not jurisdictional boundaries, and Alaska's
very broad envelope calls for local boxes or explicit sites. Future wrapped
geometry support would require a separate query-model decision.
