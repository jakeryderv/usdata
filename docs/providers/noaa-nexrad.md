# Radar scans

`noaa:nexrad-level2` downloads whole Level II scans over anonymous HTTPS from the
public archive. Provide both timestamps and a radar ID or geographic query.
Start with a dry run to inspect the number and size of files:

```sh
usdata fetch noaa:nexrad-level2 -p site=KTLX \
  --start 2024-05-06T20:00Z --end 2024-05-06T20:05Z --dry-run
```

A query spans at most 31 days; split longer intervals. Remove `--dry-run` to
download. There is no server-side variable subsetting; each file contains the
available scan moments.

--8<-- "_snippets/utc-window.md"

`site` and `sites` are mutually exclusive and accept non-empty strings or lists.
IDs are case-insensitive. With a geographic query, `nearest` selects a positive
number of nearby radars and cannot be combined with explicit IDs. Selection
falls back to the nearest radar when none lies inside the bounding rectangle.

The bundled station list excludes test/research radars from default selection.
See [archive and station metadata notes](noaa-services.md#access-notes).

## Coverage outside the declared extent

The catalog extent, 180°W to 27°W and 15°N to 72°N, holds every bundled radar
in the western hemisphere, from the Aleutians to Lajes in the Azores (`LPLA`).
Four radars lie across the antimeridian from it: Andersen AFB on Guam (`PGUA`),
Kunsan (`RKJK`) and Camp Humphreys (`RKSG`) in Korea, and Kadena on Okinawa
(`RODN`). A box cannot wrap across 180°, and one spanning every longitude would
match any search anywhere, so these four stay outside the extent. Registry
search by place or point does not list the radar datasets there; fetch them by
site id (`-p site=PGUA`), or with a geographic query, which falls back to the
nearest radar. A registry test keeps this list and the bundled table in agreement.
The optional `usdata[radar]` reader opens local scans with xradar; an explicit
zero-based `sweep` chooses a sweep. See [reader limits](../reference/readers.md),
[temporal selection](../reference/selection.md), and the
[executed radar example](https://usdata.dev/datasets/noaa/nexrad-level2/).

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Temporal resolution: the [NCEI NEXRAD product
  page](https://www.ncei.noaa.gov/products/radar/next-generation-weather-radar), which
  says a Level II file typically holds four, five, six, or ten minutes of base data
  depending on the volume coverage pattern.
- Updates, citation, and terms: the [NODD registry
  entry](https://registry.opendata.aws/noaa-nexrad/) ("New Level II data is added as
  soon as it is available") and the [NOAA Open Data
  Dissemination](https://www.noaa.gov/information-technology/open-data-dissemination)
  statement it quotes.
- Variables: the sweep field table in the [executed radar
  example](https://usdata.dev/datasets/noaa/nexrad-level2/), as the `radar` reader names
  the moments.
- Longest query window: `MAX_WINDOW` in `usdata.providers.noaa.nexrad`.
- Spatial resolution and latency are empty: the NCEI page refers gate and azimuth
  spacing to Federal Meteorological Handbook No. 11, and neither NCEI nor NODD publishes
  a latency figure for the archive.

[All NOAA datasets](noaa.md).

--8<-- "generated/catalog/noaa/nexrad-level2.md"
