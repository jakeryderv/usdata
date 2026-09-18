# Disaster declarations

`fema:disaster-declarations` uses the
[OpenFEMA v2 API](https://www.fema.gov/about/openfema/api) at
`https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries`, checked on
2026-09-18, when it held 70,405 rows.

One row is one declaration in one designated area: a county or county
equivalent, a tribal area, or a whole state. The rows carry no coordinates.
They are keyed by `fipsStateCode` and `fipsCountyCode`, which is what joins them
to Storm Events (`STATE_FIPS`, `CZ_FIPS`) and to any other county-level source.

- Both dates are required. A window selects declarations whose **incident
  period** overlaps it, inclusive at both ends, not declarations made inside
  it. DR-4776 was declared on 2024-04-30 for an incident running 2024-04-25 to
  2024-05-09, so a query for 6 May finds it and a filter on the declaration
  date would not.
- A place is a named state or county: `--location Oklahoma`,
  `--location "Osage County, OK"`, or a quoted FIPS code. `-p state=OK` and
  `-p fips=40113` say the same thing explicitly; give a location or one of
  them, not both. A `bbox` or `lat`/`lon` is refused, since a rectangle names
  no place and cannot be turned back into counties
  ([ADR 0034](../adr/0034-query-keeps-the-resolved-place.md)). With no place
  the query covers every state.
- A county also returns its state's `Statewide` designations, which cover it.
  See [county code 000](#county-code-000).
- `-p incident_type=Tornado` and `-p declaration_type=DR` narrow the rows;
  each takes one value or several, comma-separated. Incident types are written
  as FEMA writes them, such as `Severe Storm`. Declaration types are `DR`
  (major disaster), `EM` (emergency), and `FM` (fire management).
- `-p include_open=true` also returns incidents with no end date. See
  [incidents with no end date](#incidents-with-no-end-date).
- `variables` is rejected: the CSV columns are fixed, and rows are filtered
  locally. Free text is rejected as everywhere.
- Listing asks for the count first, then makes one asset per page of 10,000
  rows ordered by `declarationDate,id`. Zero matching rows is an empty
  listing; a manifest source then needs `allow_empty: true`.
- The pandas reader keeps `fipsStateCode`, `fipsCountyCode`, and `placeCode` as
  text, so `019` stays `019`. The program columns (`paProgramDeclared` and the
  rest) arrive as `0` and `1`.
- Joining to Storm Events needs `CZ_FIPS.str.zfill(3)`: both sources keep the
  county code as text, and Storm Events writes `1` where FEMA writes `001`, so
  an unpadded join silently drops every county below 100.
- Sizes are not known before download; `--dry-run` reports them as unknown.
- Access was verified without credentials.

```sh
usdata fetch fema:disaster-declarations --start 2024-05-06 --end 2024-05-06 --location "Osage County, OK"
usdata fetch fema:disaster-declarations --start 2024-05-06 --end 2024-05-06 -p state=OK -p incident_type=Tornado
```

## What the service does not say

Three behaviours were found by getting them wrong, and the adapter is built
around them ([ADR 0035](../adr/0035-openfema-window-and-place-rules.md)).

**A timestamp in a filter must be a date alone.**
`declarationDate ge '2024-05-01T00:00:00.000Z'` matches nothing, however the
colons are sent: the server compares against the still-percent-encoded literal,
and echoes it back as `T00%3A00%3A00` in the response metadata.
`declarationDate ge '2024-05-01'` works. The adapter sends dates alone, so a
window given to the minute selects by its calendar dates.

### Incidents with no end date

`incidentEndDate eq null` is valid here, and treating such rows as still open
is the obvious rule. It is the wrong default. 619 rows have no end date, and
for Oklahoma on 2024-05-06 that rule returns 75 rows of which 25 are DR-4776;
the other 50 are fire management declarations going back to 2005 whose
incidents were never closed, so they overlap every later window forever. They
are left out unless `include_open` asks for them. The cost is that a genuinely
open incident is left out too: pass `include_open=true` when asking about a
disaster still under way, and expect the old fire declarations with it.

### County code 000

1,610 rows carry `fipsCountyCode` `000`, which is not a county. FEMA's field
notes say a statewide declaration is entered that way "as multiple (all)
counties cannot be entered", and that tribal areas, which have no FIPS county
code, are identified through `placeCode` instead. Of those rows, 464 have
`designatedArea` `Statewide` and the rest name a reservation or other tribal
area.

A county query returns that county's rows and its state's `Statewide` rows,
since a statewide designation does cover the county. It returns no tribal
area, which is not a county even where it lies inside one. A state query
returns all of them.

The dataset is rebuilt every twenty minutes, but a row's `lastRefresh` and
`hash` move only when that record changes, so a pinned page is stable between
real revisions. Rows are revised as incidents close and programs are added,
which a locked restore reports as drift.

--8<-- "_snippets/upstream-revisions.md"

Probes used to verify the endpoint and these behaviours:

```sh
B='https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries'
curl "$B?\$filter=declarationDate%20ge%20'2024-05-01'%20and%20declarationDate%20lt%20'2024-06-01'&\$top=1&\$inlinecount=allpages"          # count 202
curl "$B?\$filter=declarationDate%20ge%20'2024-05-01T00:00:00.000Z'&\$top=1&\$inlinecount=allpages"                                       # count 0: timestamp not decoded
curl "$B?\$filter=state%20eq%20'OK'%20and%20incidentBeginDate%20le%20'2024-05-06'%20and%20incidentEndDate%20ge%20'2024-05-06'&\$top=1&\$inlinecount=allpages"   # count 25, all DR-4776
curl "$B?\$filter=incidentEndDate%20eq%20null&\$top=1&\$inlinecount=allpages"                                                             # count 619
curl "$B?\$filter=fipsCountyCode%20eq%20'000'&\$top=1&\$inlinecount=allpages"                                                             # count 1610
curl "$B?\$filter=disasterNumber%20eq%204776&\$top=2&\$format=csv"
```

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- The dataset description, the twenty-minute cadence (`R/PT20M`), and the
  meaning of county code `000` and `placeCode`: the
  [Disaster Declarations Summaries v2 page](https://www.fema.gov/openfema-data-page/disaster-declarations-summaries-v2).
- Variable descriptions: FEMA's own field metadata, from
  `https://www.fema.gov/api/open/v1/OpenFemaDataSetFields` filtered to this
  dataset and version.
- Citation and terms: the
  [OpenFEMA terms and conditions](https://www.fema.gov/about/openfema/terms-conditions),
  which ask for the endpoint with its version, the date and time of access, and
  the disclaimer the catalog entry's citation ends with.
- License: the terms page states conditions of use and names no license. The
  entry records the data as a work of the U.S. Government.
- Latency is empty: FEMA states how often the dataset is rebuilt, not how soon
  a new declaration appears in it.
- No window limit is declared, because the adapter enforces none.

[FEMA access notes](fema.md).

[Catalog reference](../generated/catalog/fema/disaster-declarations.md#catalog-reference).
