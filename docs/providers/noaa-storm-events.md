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
provider-specific params are rejected, so `spatial_subset` and
`variable_subset` are false: selecting an annual object performs no server-side
row subsetting. Only `temporal_subset` is true, because the requested dates
choose which annual objects are returned.

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

## The timezone rule

`CZ_TIMEZONE` is a local-standard-time label ending in its whole-hour UTC
offset, so `CST-6` is UTC−6 and Guam's `GST10`, which omits the sign, is UTC+10.
The labels seen in the annual files are `CST-6`, `EST-5`, `MST-7`, `PST-8`,
`AST-4`, `AKST-9`, `HST-10`, `SST-11`, and `GST10`, plus a few daylight spellings
(`CDT-5`, `EDT-4`, `PDT-7`) whose trailing offset is still the one to use. No
Python timezone accepts these strings, and applying a named regional zone would
add daylight saving the reports do not use.

Files through 2006 write the label bare, with no offset: `CST`, not `CST-6`.
Eight bare labels name one offset wherever they appear in the archive and are
converted with it: `CST` −6, `EST` −5, `MST` −7, `PST` −8, and `HST` −10, and
the daylight labels `CDT` −5, `EDT` −4, and `MDT` −6, a few rows a year, read at
their word as `CDT-5` is. The rest are left unconverted rather than guessed
([ADR 0033](../adr/0033-bare-storm-events-timezone-labels.md)):

- `AST` labels both Alaska (UTC−9) and Puerto Rico and the Virgin Islands (UTC−4).
- `SST` labels both American Samoa (UTC−11) and Guam (UTC+10).
- `UNK` says nothing.

`STATE` tells the first two apart, so a caller who needs those rows can convert
them by hand. The local timestamps carry two-digit years; `50` to `99` are read
as 1950 to 1999, since the archive begins in 1950, where the usual pivot would
put its first nineteen years a century late.

When the frame keeps `BEGIN_DATE_TIME`, `END_DATE_TIME`, and `CZ_TIMEZONE`,
`open()` adds `BEGIN_UTC` and `END_UTC` as timezone-aware UTC timestamps,
leaving the original columns alone. A row whose label yields no offset, or whose
timestamp does not parse, gets `NaT`. `frame.attrs["usdata"]["derived"]` lists,
per derived column, the rule used, the count of such rows as `unparsed`, and
under `labels_without_offset` each label that gave no offset with how many rows
carry it.

```python
frame = item.open(usecols=["EVENT_ID", "BEGIN_DATE_TIME", "END_DATE_TIME", "CZ_TIMEZONE"])
print(frame[["BEGIN_DATE_TIME", "CZ_TIMEZONE", "BEGIN_UTC", "END_UTC"]].head())
print(frame.attrs["usdata"]["derived"])  # column, source, rule, unparsed, labels_without_offset
hours = pd.to_numeric(frame.CZ_TIMEZONE.str.extract(r"^[A-Za-z]+([+-]?\d{1,2})$", expand=False))
local = pd.to_datetime(frame.BEGIN_DATE_TIME, format="%d-%b-%y %H:%M:%S", errors="coerce")
```

The last two lines are the manual form for files from 2007 on: subtract
`pd.to_timedelta(hours, unit="h")` from `local` and call `.dt.tz_localize("UTC")`
to get the same instants without the reader. Earlier files also need the bare
labels mapped and, before 1969, the century corrected, which `%y` gets wrong.

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
