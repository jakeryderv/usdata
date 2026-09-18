# 0036: NWS events are selected by issuance, one county at a time

Status: accepted. Date: 2026-09-18. Applies
[ADR 0034](0034-query-keeps-the-resolved-place.md).

## Context

`noaa:nws-vtec-events` is the second source selected by place
([issue 252](https://github.com/jakeryderv/usdata/issues/252)), after FEMA
disaster declarations ([ADR 0035](0035-openfema-window-and-place-rules.md)). It
reads the Iowa Environmental Mesonet's archive of National Weather Service
watches, warnings, and advisories, served per UGC, the NWS code for a county or
a forecast zone. The registry's planned `noaa:nws-warnings` had already recorded
that IEM's mirror, not an NWS endpoint, is the maintained archive; the official
API keeps none.

Probing the live service before writing the adapter found three behaviours its
documentation does not state plainly, each by sending the obvious query and
getting an answer that looked right and was not.

1. **The date-only parameters are unreliable.** `sdate=2024-05-07` with
   `edate=2024-05-08` returns no rows for Osage County. The same span given as
   `sts` and `ets` returns 13. Six windows were tried, and no rule about time
   zones or inclusive ends explains the date-only results; a whole year given
   the same way does return the right count. The explicit parameters were added
   on 2025-01-20, take any UTC offset, and are half-open.
2. **The window selects by issuance.** A Tornado Watch ran from 19:05 UTC on
   6 May 2024 to 03:48 UTC on 7 May. A window of 03:00 to 03:30 UTC, inside it,
   returns nothing. The service cannot be asked what was in effect.
3. **A county code reaches county-based products only.** `OKC113` for 2024
   returns six event types, all convective or flood. Osage County's forecast
   zone that year, `OKZ054`, returns twelve others, heat, fire weather, and
   winter weather among them. The zone is not a fixed property of the county:
   `OKZ054` covered all of it through April 2026, and three zones replaced it in
   May 2026.

It also found that [ADR 0034](0034-query-keeps-the-resolved-place.md) had kept
too little. A county UGC is the state's postal code, `C`, and the county FIPS
code, and `Place` had no postal code. That is recorded as an amendment there,
since it is a statement about the model, not about this source.

## Decision

**Only `sts` and `ets` are sent**, as UTC instants to the second. A usdata
window's end is inclusive and `ets` is exclusive, so the adapter sends the end
plus one second: an event issued at exactly the requested end is returned, and a
bare end date, which means the last instant of that day, becomes the next
midnight.

**A window selects events by issuance, and the adapter says so rather than
hiding it.** The alternative was to widen the window backwards inside the
adapter so that events still in effect are caught. How far is a guess that
depends on the product: the tornado warnings in the probe ran 26 to 49 minutes
and the watch nearly nine hours, and flood products run longer. A built-in
lookback would be wrong for some product whatever its value, and would return
rows the caller did not ask for under an id that says otherwise. The guide gives
the recipe instead: widen the window, then compare `iso_issued` and
`iso_expired`. This is [ADR 0035](0035-openfema-window-and-place-rules.md)'s
lesson from the other side. There the service could select by the period that
mattered, and the adapter used it. Here it cannot, and pretending it can would
be the guess.

**A location must be a county.** A state is refused by name, with a hint. IEM's
by-state service has a different shape: it requires a `year` and takes no
window, so serving a state through it would give one dataset two meanings of a
time range. A `ugc` parameter names a code explicitly, which is also the only
way to reach a forecast zone, since the place table holds counties and a county
cannot name the zone that covers it. Giving both a location and a `ugc` is
refused.

**`phenomena` and `significance` are accepted only as a pair**, as the service
requires; one without the other is refused before any request, where the service
would answer 422.

**Listing makes no request.** The service offers no count, so there is nothing
to ask before fetching. A window with no events is therefore one asset holding a
header, not an empty listing, and a manifest source for a quiet window needs no
`allow_empty`. An explicit `ugc` the service does not know behaves the same way,
silently. A county location cannot be wrong like that, because it comes from the
place table, which is one more reason to prefer it.

**The dataset id is `noaa:nws-vtec-events`.** `noaa:nws-warnings` is the polygon
archive. A row here is a VTEC event, and the name stays true when a zone is
reached through `ugc`.

## Alternatives

- **Send dates when the window is whole days.** Simpler URLs, and the unreliable
  path for exactly the short spans people ask about.
- **A `lookback` parameter.** It moves the guess from the adapter to the caller,
  who can already widen the window, and adds a second way to say the same thing.
- **Filter to events in effect after fetching.** Providers return the service's
  bytes; they do not edit rows ([ADR 0027](0027-provider-contract.md)).
- **Map a county to its forecast zones.** Needs the NWS zone-county correlation
  file as bundled data, and one file is not enough: the mapping is one-to-many
  and changes, as Osage County's did in 2026, so the right zone depends on the
  date asked about. No current use case asks for zone-based products.
- **Validate an explicit `ugc` against a bundled list.** The same bundled file,
  to catch a typo the empty result already reveals.

## Consequences

"What was in effect at this moment" takes two steps, a wider window and a
comparison, and the worked example shows them. It also shows the limit the rows
themselves impose: a county is listed on a warning when the warning's polygon
touches it, so a county-level lead time says a warning naming the county was in
effect, not that it covered the place the tornado struck. Verification needs the
polygons.

Events before 2005 are IEM's reconstruction from an NWS database dump, with
present-day offices and heuristically merged counties. The guide quotes IEM on
this, and `eventid` and `wfo` before 2005 should be read accordingly.

This is the second adapter to use `Provider.place_of` and declare
`place_subset`, and it needed no change to either. What it needed was one more
field on `Place`, which is what a second source was meant to find out.
