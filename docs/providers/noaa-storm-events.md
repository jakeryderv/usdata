# Storm Events annual details

Available since v0.8 as `noaa:storm-events`. Anonymous NCEI bulk
access returns whole annual **details** tables, compressed with gzip. The
separate fatalities and locations tables are not included. The adapter supports
schema `v1.0`; it does not guess how to interpret a newer schema.

Both dates are required and interpreted in UTC for annual file selection.
Every calendar year touched is returned in full: May 1–31 selects the complete
year; December 31–January 1 selects both years. Asset time bounds label those
whole file years, not precise coverage of local event timestamps. Dates before
1950 and a missing requested year are errors, so a multi-year request cannot
silently succeed with only some years. Location/bbox, variables, text, and all
provider-specific params are rejected. `capabilities` are false because selecting
an annual object does not perform server-side row subsetting.

The directory lists filenames such as
`StormEvents_details-ftp_v1.0_d2024_c20260728.csv.gz`: `d` identifies the data year
and `c` the creation date. Resolution chooses the greatest valid creation date
per year. The complete filename is the stable asset ID; URL, original compressed
bytes, size, and checksum are preserved. Exact integer directory sizes are used
when present; approximate sizes are left unknown. A lockfile restores its pinned
URL without listing current revisions, so `pull --force` is what moves to a
newer annual revision.

--8<-- "_snippets/upstream-revisions.md"

`FetchedAsset.open()` uses the pandas extra and a local gzip stream. It preserves
raw identifier strings and records source provenance in DataFrame attributes;
it does not decompress into the cache. `EVENT_ID` identifies event records,
while `EPISODE_ID` can group several events. `CZ_TYPE` distinguishes county,
forecast-zone, and marine records; `CZ_FIPS` is not always a county code.
Dates/times in rows are local, with `CZ_TIMEZONE` needed for instant conversion.
The [executed notebook](https://usdata.dev/examples/storm-events/) filters on
reported calendar dates and keeps timezone labels visible.

Reported events, impacts, and damage ratings require care when aggregating:
physical storms can span several records, historical reporting varies, and
missing reports do not establish an absence of hazards. Source field meanings
are documented in the [NCEI bulk format reference](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/Storm-Data-Bulk-csv-Format.pdf).
The [archive README](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/README)
describes filenames and revisions; [dataset metadata](https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc%3AC00510/html)
describes historical coverage.


See the [service research notes](noaa-services.md#storm-events-annual-details) for dated upstream probes.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Updates: the [archive
  README](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/README), which
  says the current yearly file is updated each month.
- Resolution and variables: the [NCEI bulk format
  reference](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/Storm-Data-Bulk-csv-Format.pdf)
  for the record granularity and the identifying columns this guide names. The full
  column set is larger.
- Terms and citation: the [NCEI dataset
  record](https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C00510/html),
  whose use constraint is only "cite dataset when used as a source", so the entry uses
  the agency, product, and access form.
- Latency is empty: neither the README nor the dataset record states how far behind the
  present the files run.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/storm-events.md#catalog-reference).
