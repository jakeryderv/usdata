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
rather than silently dropping island polygons (amended below). Explain this
limitation in the [place reference](../reference/places.md).

Resolve states first, then qualified county names, with explicit ambiguity
errors and quoted FIPS as an unambiguous alternative. Regeneration remains a
maintainer operation; runtime and unit tests need no source downloads.

## Consequences

The package gains full state/county coverage with no new dependencies. Generated
bounds can change station selection relative to the seed rectangles. Envelopes
are approximate spatial filters, not jurisdictional boundaries, and Alaska's
very broad envelope calls for local boxes or explicit sites. Future wrapped
geometry support would require a separate query-model decision.

## Amendment, 2026-09-25: clip at the antimeridian instead

The broad envelope did not stay conservative in practice. Alaska and Aleutians
West spanned 359 degrees of longitude, so `location="Alaska"` sent every
adapter a band around the globe from 51°N to 71°N: earthquake searches returned
events in Kamchatka and Iceland, and registry search matched every dataset
touching that band.

A place whose vertices span more than 180 degrees of longitude now keeps only
its western-hemisphere polygons. For the 2025 vintage that is Alaska and
Aleutians West, which lose the Near Islands and part of the Rat Islands west
of 180. The generator refuses a polygon lying on both sides of the prime
meridian, any box still wider than 180 degrees, and any set of clipped places
other than the expected one, and it records each clip and the dropped box in
`places.sources.json`. The islands are not silently dropped: the rule is stated
in the place reference and the bundled metadata. Wrapped geometry support
remains a separate query-model decision.

## Amendment, 2026-09-25: Connecticut's counties before 2022 are kept beside its planning regions

In 2022 Connecticut's nine planning regions replaced its eight counties as
county equivalents, and the 2025 files hold only the regions. Three
place-keyed sources did not follow
([issue 360](https://github.com/jakeryderv/usdata/issues/360)). Every OpenFEMA
row for Connecticut declared since then carries `000` or a county code from
`001` to `015`; IEM returns 57 events for `CTC003`, Hartford County, from
January 2024 to June 2025 and none for `CTC110`; and every open AQS monitor in
the state has an old county code. A location naming a region therefore
selected statewide FEMA rows alone, or nothing at all, with no error. The old
counties could not be named, because the table did not hold them.

The table now also holds the eight counties, from the 2021 county file, the
last vintage to hold them, pinned by URL and hash like the 2025 archives. They
resolve like any county, by name or by `"09001"` to `"09015"`, and a `Place`
built from one is an ordinary county: the `Place` model is unchanged. Only the
table marks them, with kind `legacy_county`. The generator refuses a vintage
whose Connecticut is not the nine regions, a 2021 file whose Connecticut is not
the eight counties, and any county name a region shares, so every existing
lookup resolves as before.

A region does not nest in the counties, nor they in it. Each region lists the
counties it overlaps in a `legacy_counties` column, from the Census town
crosswalk: regions and counties are both made of whole towns, so a region
overlaps a county exactly when they share a town. The generator checks every
code and name in the crosswalk against the rows. The boxes cannot answer this:
intersecting them gives 39 region-county pairs where the towns give 19, and the
Capitol region's box touches seven of the eight counties.

A source keyed by the old codes refuses a region by name and lists the
counties it overlaps; see [ADR 0034](0034-query-keeps-the-resolved-place.md).

Alternatives considered:

- **Translate a region into its counties inside each adapter.** A region's
  rows would be the union of up to four counties, most of them lying mostly
  outside it, under a place that says otherwise. The refusal names the same
  counties and leaves the choice to the caller.
- **Refuse Connecticut counties on these sources, and add nothing.** It would
  stop the silent empty answers and leave the old counties, which are what
  these sources hold, unreachable by `location`.
- **Keep the old counties as the only Connecticut counties.** Rectangle-based
  sources and any source that has moved to the regions would lose them, and
  it would turn the current Census geography into the exception.
