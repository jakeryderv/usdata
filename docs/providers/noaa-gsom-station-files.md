# GSOM station files

Available since v0.33 as `noaa:gsom-station-files`. The Global Summary of the
Month is NCEI's set of monthly station summaries derived from GHCN-Daily:
means, extremes, totals, and day counts. [`noaa:gsom`](noaa-gsom.md) reads it
through the Access Data Service, which selects months, stations, and elements
on the server. This dataset reads NCEI's static per-station files instead: one
CSV per station holding its whole record, every element, in metric units.

```sh
uv run usdata fetch noaa:gsom-station-files -p stations=USW00094823,USC00100667 --dry-run
```

## When to use which

| | `noaa:gsom` | `noaa:gsom-station-files` |
|---|---|---|
| Request | One query per 50 stations, built by the service | One static file per station |
| Selects | Months, stations or a box, and elements | Stations only |
| Units | Metric or standard | Metric |
| Speed for long records | Varies widely (below) | 315 stations, 199 MB, in 49 s |

Use `noaa:gsom` for a few elements over a short window, or to find stations
in a box. Use the station files for many stations' long records. On
2026-09-28, a 50-station, 77-year `SNOW` request to the service streamed at
anywhere from 35 kB/s to 4 kB/s, and one stalled past three 120-second read
timeouts. The same station's static file, 407 kB, arrived in 0.7 s. The values
agree: Pittsburgh's (`USW00094823`) snowfall for November 1997 to March 1998 is
64, 320, 45, 64, and 125 mm by either route.

## Selection

`stations` is required and takes one GHCN id, a list, or a comma-separated
string. Ids are upper-cased, must be 11 characters, and repeat only once. The
asset id is `<station>.csv`, which is NCEI's filename. The files cannot be
selected by time, place, or element, so a window, a box, variables, and text
are refused, and every capability is false.

NCEI's directory holds one file for every GSOM station worldwide and is too
large to list: a request for its index returned nothing in 30 seconds. So
listing makes no request and reports no size, and a station without a file
fails at fetch with a 404 rather than at listing. For the same reason an
asset's time is the archive's bound, from GHCN-Daily's first observation in
1763 and open-ended, not the station's own span, which the file's first and
last `DATE` give.

## What a file holds

One row per month, from the station's first summarised month to its last,
with `STATION`, `DATE` (`YYYY-MM`), `LATITUDE`, `LONGITUDE`, `ELEVATION`,
`NAME`, and then each element with its `_ATTRIBUTES` column. The element set
depends on the station: `USC00100667`'s file has 68 columns. A month's value is
blank when NCEI could not compute it: for precipitation and snowfall, more
than five days missing or flagged. Each attribute column is
`DaysMissing,MeasurementFlag,QualityFlag,SourceFlag`, so `,,,Z` is a value with
no missing days from source `Z`, and a leading number counts the days missing. Units
are metric: millimetres for `SNOW` and `PRCP`, degrees Celsius for
temperatures, metres for `ELEVATION`. The asset's `properties` record
`units: metric`, which the file does not state.

`open()` returns a pandas DataFrame with `STATION` kept as a string:

```python
frame = item.open()
winter = frame[frame["DATE"].str[5:].isin(["12", "01", "02"])]
```

## Revisions

NCEI rewrites each file in place as the station's summaries change. The
record states weekly updates, and `USC00100667`'s file carried a Last-Modified
of 2026-09-16. A lockfile pins each station's file separately, so a revised
station reports that one entry as changed and leaves the others alone.

--8<-- "_snippets/upstream-revisions.md"

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- The file location, element definitions, missing-day rules, and attribute
  layout: NCEI's [GSOM documentation](https://www.ncei.noaa.gov/data/global-summary-of-the-month/doc/GSOM_documentation.pdf),
  which names `https://www.ncei.noaa.gov/data/global-summary-of-the-month/access`
  as where the data files are.
- Updates, citation, and terms: the [NCEI dataset
  record](https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C00946/html),
  the same one `noaa:gsom` cites.
- Units: the files, checked against the service's metric output for the same
  station and months.
- Latency is empty: the record states no lag between a month's end and its summary.

[All NOAA datasets](noaa.md).

--8<-- "generated/catalog/noaa/gsom-station-files.md"
