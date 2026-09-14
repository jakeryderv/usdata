# SPC tornado reports

Available since v0.15.0 as `noaa:spc-tornado-reports`. The Storm Prediction
Center publishes its tornado database as plain CSV files linked from its
[severe weather database page](https://www.spc.noaa.gov/wcm/#data): one file
per year from 2008 onward, half-decade files for 2000–2004 and 2005–2007, and
decade files for 1950–1999. The adapter reads that page, keeps only local links
named `<years>_torn.csv`, and returns each whole file whose year range touches
the requested interval. Hail and wind files, the zipped all-years archive, and the
`actual_tornadoes` and `all_tornadoes` dumps are not selected.

Both dates are required and interpreted in UTC for year selection. Every file
covering a requested year is returned in full: May 1–31, 2024 selects
`2024_torn.csv`; June 1955 selects the whole `50-59_torn.csv` decade;
December 31, 1999 to January 1, 2000 selects the 1990s decade and the 2000–2004
file. When several linked files cover a year, the narrowest one wins, so a
per-year file is preferred over any wider archive. Asset time bounds label the
file's years, not precise event coverage. Dates before 1950 and a requested
year with no linked file are errors, so a span cannot silently succeed with
only some years. Location/bbox, variables, text, and all provider-specific
params are rejected. `capabilities` are false because selecting a whole file
does not perform server-side row subsetting.

File names are stable and the bytes are revised in place: SPC refreshes prior
years when NWS Storm Data is finalized, and the page shows an update date next
to each file. Nothing in the name records that revision, so the asset id is the
plain file name and the lockfile checksum is the only revision record. A
locked restore downloads the pinned URL without reading the page. Sizes on the
page are approximate, so assets carry no size.

--8<-- "_snippets/upstream-revisions.md"

`FetchedAsset.open()` uses the pandas extra. Every row is one tornado or one
segment of a tornado, following the
[SPC format specification](https://www.spc.noaa.gov/wcm/data/SPC_severe_database_description.pdf):

- `om` numbers tornadoes within a year; state-crossing and four-plus-county
  tornadoes repeat it across segments. `yr`, `mo`, `dy`, `date`, and `time`
  give the touchdown date and time.
- `tz` is the time-zone code. All rows except `?` (unknown) and `9` (GMT) were
  converted to `3`, Central Standard Time (UTC−6, no daylight saving), even for
  tornadoes outside the Central zone. Convert to UTC by adding six hours before
  matching radar or satellite scans.
- `st` is the two-letter state and `stf` its FIPS code; `stn` is a within-state
  count discontinued in 2008.
- `mag` is the F-scale through January 2007 and the EF-scale afterwards, with
  `-9` for unknown. `fc` is `1` when a 1950–1982 rating of `-9` was replaced by
  an estimate in 2016.
- `inj`, `fat`, `loss`, and `closs` are injuries, fatalities, property loss,
  and crop loss. Before 1996 `loss` is a damage category from 0 to 9, not a
  dollar amount; from 1996 it is millions of dollars, and 0 does not mean $0.
- `slat`, `slon`, `elat`, `elon` are start and end coordinates in decimal
  degrees; `len` is the path length in miles and `wid` the width in yards.
- `ns`, `sn`, `sg` describe segments: `sg == 1` is the entire track (one row
  per tornado), `sg == 2` is one state's segment of a multi-state tornado, and
  `sg == -9` carries extra county FIPS codes for tornadoes crossing more than
  four counties. `f1` to `f4` are county FIPS codes. Count tornadoes with
  `sg == 1`; sum state totals with `sn == 1`.
- Files for 2025 onward add `edat` and `etime`, the end date and time.

FIPS codes are unpadded integers in the source, so the CSV reader parses them as
numbers; pass `dtype={"stf": "string", "f1": "string"}` to keep them as text.
Recent files occasionally contain rows outside the documented `sg` values; the
adapter preserves the source rather than correcting it.

## SPC versus Storm Events

Both derive from NWS Storm Data, but they are shaped differently. SPC is one
row per tornado (plus state segments) with a single start-to-end path, a
rating, and impact counts, and no narrative. `noaa:storm-events` is one row per
county or zone segment, with local time and a `CZ_TIMEZONE` column, narratives,
and `TOR_F_SCALE` text such as `EF1`. SPC rows are all in Central Standard Time;
Storm Events rows are in each report's local zone. Neither database is a complete
record: SPC notes that tornadoes were underreported before 1953, that damage
figures are unreliable, and that its files serve NWS verification rather than
climatology. Matching a tornado between the two needs date, state, and
coordinates, not a shared identifier.

See the [service research notes](noaa-services.md#spc-tornado-reports) for dated
upstream probes and the
[example manifest](https://usdata.dev/examples/spc-tornadoes/) for one year's
tornado counts by rating.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/spc-tornado-reports.md#catalog-reference).
