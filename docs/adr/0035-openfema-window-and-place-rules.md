# 0035: OpenFEMA declarations select by incident period, exclude open incidents, and widen a county to its state's statewide rows

Status: accepted. Date: 2026-09-18. Applies
[ADR 0034](0034-query-keeps-the-resolved-place.md).

## Context

`fema:disaster-declarations` is the first source keyed by place
([issue 241](https://github.com/jakeryderv/usdata/issues/241)). Probing the live
OpenFEMA service before writing the adapter turned up four behaviours that the
service's documentation does not state and that each change what a query means.
All were found by sending the obvious query and getting a wrong answer that
looked like a right one: a well-formed response with the wrong rows, or none.

1. **Full timestamps in a filter match nothing.**
   `declarationDate ge '2024-05-01T00:00:00.000Z'` returns a count of 0 where
   the same filter with `'2024-05-01'` returns 202. The response metadata echoes
   the filter back as `T00%3A00%3A00`: the server compares against the
   still-percent-encoded literal, however the colons are sent.
2. **The declaration date is not when the disaster happened.** DR-4776 was
   declared on 2024-04-30 for an incident running 2024-04-25 to 2024-05-09. A
   query for 6 May 2024 filtered on `declarationDate` finds nothing in Oklahoma;
   filtered on the incident period it finds the 25 designated counties.
3. **A missing end date does not mean recent.** 619 rows have no
   `incidentEndDate`. Treating them as open incidents, for Oklahoma on
   2024-05-06, returns 75 rows of which 25 are DR-4776. The other 50 are fire
   management declarations going back to 2005 whose incidents were never
   closed, so they overlap every later window forever.
4. **County code `000` is not a county.** 1,610 rows carry it. FEMA's field
   notes say a statewide declaration is entered that way "as multiple (all)
   counties cannot be entered", and that tribal areas, which have no FIPS county
   code, are identified through `placeCode`. 464 of those rows are `Statewide`;
   the rest name a reservation or other tribal area.

## Decision

**A window selects by incident period, by date alone, inclusive at both ends:**
`incidentBeginDate le <end date> and incidentEndDate ge <start date>`. A window
given to the minute selects by its calendar dates, because the service can
compare nothing finer. Both boundaries were checked: a window of 2024-04-25
alone and one of 2024-05-09 alone each find DR-4776, and 2024-05-10 does not.

**Incidents with no end date are excluded unless `include_open` is true.** The
default has to be one of two wrong answers. Including them buries every result
under stale fire declarations and teaches a user to distrust the source.
Excluding them misses an incident that is genuinely under way, which is exactly
when someone is likely to ask. The exclusion is the more honest failure: it is
an omission the documentation can state, where the inclusion is noise no
documentation can remove. `include_open=true` brings the open incidents back,
stale ones included.

**A county selection also returns its state's `Statewide` rows**, and no tribal
area: `fipsStateCode eq 'SS' and (fipsCountyCode eq 'CCC' or designatedArea eq
'Statewide')`. A statewide designation does cover the county, so leaving it out
would answer "was this county under a declaration" wrongly. A tribal area is
not a county even where it lies inside one, and nothing in the row says which
county that is. A state selection returns every row of the state, tribal areas
included.

**Pages are ordered by `declarationDate,id`.** Row ids were unchanged across a
rebuild of the dataset during probing, and consecutive pages under that order
were disjoint. A row's `lastRefresh` and `hash` move only when the record
changes, so a pinned page is stable between real revisions even though the
dataset is rebuilt every twenty minutes.

Parameter values reach the filter as quoted literals, so they are validated to
shapes that cannot close a quote: two letters, five digits, a fixed set of
declaration types, and incident types of letters, spaces, and `/ ( ) -`.

## Alternatives

- **A recency rule for open incidents**, such as open and begun within some
  number of days of the window. Any number is a guess about how long FEMA takes
  to close an incident, and the project's rule elsewhere is that unsure means
  say so.
- **Exclude `FM` declarations from the open-incident rule.** It would remove
  most of the stale rows today and encodes an observation about current data
  as if it were a property of the source.
- **A county returns its own rows only.** Simpler and exact, and it silently
  answers the most natural question about this dataset wrongly whenever a
  declaration was statewide.
- **Filter on `declarationDate`**, or offer it as a second mode. The declaration
  date answers an administrative question. It stays available locally, since
  the column is in every row.
- **Fetch the whole dataset as one file.** 70,405 rows is small enough, but it
  discards server-side selection and makes every pin drift on every revision
  anywhere in the country.

## Consequences

A query for a disaster still under way returns nothing until `include_open` is
set, and the provider note says so where the empty result will send a reader.

The `Statewide` rule makes a county selection return rows whose
`fipsCountyCode` is `000`, so a caller joining on county code should expect
them and can drop them with one comparison.

Joining these rows to Storm Events needs `CZ_FIPS.str.zfill(3)`: both sources
keep the county code as text, and Storm Events writes `1` where FEMA writes
`001`. The reader leaves each source's values as delivered, so the worked
example records the step rather than the reader hiding it.
