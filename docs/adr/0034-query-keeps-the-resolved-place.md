# 0034: A query keeps the place it resolved

Status: proposed. Date: 2026-09-18. Extends
[ADR 0005](0005-generated-census-place-envelopes.md).

## Context

`build_query(location="Osage County, OK")` looks the name up in the bundled
Census table, finds geoid `40113`, and returns a `Query` holding only that
county's bounding rectangle. The identifier is discarded on the way. That has
been enough, because every source so far either takes a box (ERDDAP grids,
earthquakes), uses a box to choose stations or sites (GHCN, NEXRAD, USGS), or
refuses space altogether (HRRR, Storm Events).

[FEMA disaster declarations](https://github.com/jakeryderv/usdata/issues/241)
is the first source that fits none of those. Its rows carry no coordinates.
They are keyed by `fipsStateCode` and `fipsCountyCode`, and the service filters
on those. A rectangle cannot be turned back into counties without a spatial
join the core does not do, and the join would be wrong anyway: the place table
warns that a county's envelope "can include neighbouring counties", and Osage's
does: its box holds the centre of Pawnee County and parts of several more. The one place argument users
already know therefore cannot reach this dataset, although the lookup that
would have answered it ran and threw its answer away.

It will not be the last. The planned Census and EPA county-level sources are
keyed the same way.

The adapter contract adds a second problem. `check_declared_capabilities`
probes every adapter with a bare box and holds the result to
`capabilities.spatial_subset`. FEMA must refuse a bare box, since it cannot
honour one, which makes `spatial_subset` false. Yet a county does narrow what
FEMA serves, which is what that flag is documented to mean. One flag is being
asked two questions: can you take a rectangle, and can you take a place.

## Decision

**`Query` gains an optional `place`.** It is a small model, `Place`, holding
what the lookup already found: `kind` (`state` or `county`), `geoid` (the two-
or five-digit FIPS code), and `label` (the name as the table writes it). It is
set only when the spatial filter was given as a `location`. A `bbox` or a
`lat`/`lon` names no place, so `place` stays `None`; nothing infers a place
from a box.

`Query.bbox` is unchanged and is still set from the same lookup, so a query
built from a location carries both. Every existing adapter reads `bbox` and
never looks at `place`, and behaves exactly as it does today. The box is not
duplicated inside `Place`: the query holds one box, in the one field that has
always held it.

`resolve_place` keeps its name and its `BBox` return, since it is public and
tested as such. The lookup that returns the whole record gets a new name,
`find_place`, and `resolve_place` becomes its box.

**`Capabilities` gains `place_subset`.** True means a named state or county
selects what the source serves. It is independent of `spatial_subset`, which
keeps meaning that a rectangle does. FEMA is `place_subset: true`,
`spatial_subset: false`. The contract check gains the matching probe: a query
carrying a `place` and its box, held to `place_subset` in both directions, the
way the bare-box probe is held to `spatial_subset`. Every existing dataset is
`place_subset: false`, and the probe confirms it for them, because an adapter
that ignores `place` answers a place query exactly as it answers that box.

**An adapter that selects by place says so through the base class.**
`Provider` gains one helper, `place_of(query)`, returning the `Place` or
raising `QueryError` when the query has a box and no place, with a hint naming
`--location` and the adapter's own place parameters. That keeps the refusal
worded the same for every such source, as `reject` and `utc_window` do for
theirs.

**Parameters still work and win.** A place-keyed adapter also declares its
identifiers as params (`state`, `fips`), for a manifest that wants to be
explicit and for identifiers the place table does not hold. Giving both a
`location` and a place parameter is refused, as GHCN refuses stations with a
location: one query, one statement of where.

The manifest and lockfile formats do not change. A manifest source already
carries `location` as a string and builds its query through `build_query`, so
it gains a place with no schema change; a lockfile pins assets, not queries.

## Alternatives

- **Parameters only.** No model change: `-p state=OK`, `-p fips=40113`, and a
  refusal for `--location`. It makes the documented place argument fail on a
  whole class of sources, and leaves each one to choose its own spelling for
  the same two identifiers. It is the right fallback and stays available; it is
  the wrong only answer.
- **Put the box inside `Place` and drop `Query.bbox`.** One spatial field
  instead of two, but it breaks every adapter, every manifest-built query, and
  the registry's spatial search, to tidy a model that is not wrong.
- **Recover counties from the box with a spatial join.** Needs boundary
  geometry at runtime, which [ADR 0005](0005-generated-census-place-envelopes.md)
  chose not to ship, and returns the wrong counties for the reason above.
- **Let FEMA declare `spatial_subset: true`.** It would then have to accept the
  bare-box probe, which it cannot honour, or the contract check would need a
  per-dataset exception. A flag that means two things is how the check stopped
  being able to say what it verifies.
- **Carry only the geoid as a string.** `kind` is derivable from its length,
  but every reader would re-derive it, and `label` is what an error message or
  a provenance note wants to print.

## Consequences

`models.py` changes, which ripples: `Query`, a new `Place`, and `Capabilities`.
All three changes are additive with defaults, so existing queries, registry
entries, and third-party adapters validate unchanged.

The provider contract of [ADR 0027](0027-provider-contract.md) grows by
`Provider.place_of`, the `place` field an adapter may read, and the
`place_subset` capability its checks verify. That is an addition, a minor
release.

`--location` starts to mean slightly different things by source: a rectangle
for a grid, a way to choose stations for GHCN, an exact county for FEMA. That
was already true of the first two. The concepts page on places says so today
and gains the third case.

A county place selects that county's rows and nothing else. Whether a county
query should also return a declaration designated statewide is a question
about FEMA's data, not about this model, and belongs to the adapter and its
provider note.
