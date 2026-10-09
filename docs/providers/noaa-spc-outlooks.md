# SPC convective and fire weather outlooks

`noaa:spc-outlooks`, available since v0.35.0, uses the
[Iowa Environmental Mesonet](https://mesonet.agron.iastate.edu/request/gis/outlooks.phtml)
archive of Storm Prediction Center outlooks, at
`https://mesonet.agron.iastate.edu/cgi-bin/request/gis/outlooks.py`, checked on
2026-10-08. IEM parses every outlook product SPC issues and serves the history
for any span.

Each fetched file is a zip holding a shapefile (`.shp`, `.shx`, `.dbf`, `.prj`),
one row per outlook area: its type and day, its valid period (`ISSUE` to
`EXPIRE`), when SPC issued the product (`PRODISS`), the threshold and what it
measures (`THRESHOLD`, `CATEGORY`), and IEM's canonical issuance hour (`CYCLE`).
The Day 1 convective outlooks issued on 6 May 2024 hold categorical risks from
`TSTM` to `MDT`, tornado, wind, and hail probabilities, and `SIGN` areas for
significant severe weather; Days 3 and 4 use `ANY SEVERE` probabilities. Fire weather
outlooks hold `ELEV` and `CRIT` areas under `FIRE WEATHER CATEGORICAL`.

- Both timestamps are required, in UTC, to the second. The window selects
  outlooks by `PRODISS`, inclusive at both ends. See
  [selected by issuance](#selected-by-issuance).
- A window is fetched as one zip per UTC month it touches; nothing is requested
  while listing, and sizes are not known before download.
- `-p outlooks=convective` (the default), `fire`, or both. Convective outlooks
  start in 1987, fire weather outlooks on 2 May 2006.
- `-p days=1` narrows to outlook days 1 to 8; every day by default.
- `-p geometry=cake_layer` (the default) returns each threshold's area
  including the higher risks inside it, as SPC draws them, so a place under a
  Moderate risk lies in the general thunderstorm, marginal, slight, enhanced,
  and moderate areas. `cookie_cutter` cuts each area to exclude the higher ones,
  so every place lies in one categorical area.
- A `location`, `bbox`, or `lat`/`lon` is refused: outlooks cover the nation and
  the service has no spatial filter. Clip their areas locally. `variables` is
  rejected: the columns are fixed.
- There is no bundled shapefile reader, so `open()` refuses the zip.
  `geopandas.read_file(path)` reads it directly, and so does pyshp's
  `shapefile.Reader(path)`. Timestamps are `YYYYMMDDHHMM` strings in UTC.

```sh
usdata fetch noaa:spc-outlooks --start 2024-05-06 --end 2024-05-06T23:59Z -p days=1
usdata fetch noaa:spc-outlooks --start 2024-04-01 --end 2024-06-30 -p outlooks=convective,fire -p geometry=cookie_cutter
```

## Selected by issuance

The window selects by `PRODISS`, the time SPC issued the product, not by the
period the outlook is valid for. That is the selection a forecast made before a
moment needs: an outlook issued before the moment is in the window, whatever
period it covers. On 6 May 2024 the Day 1 outlook valid from 12 UTC was issued
at 05:55, and `[05:00, 06:00)` returns it while `[12:00, 12:01)`, its valid
start, returns nothing. The end is exclusive at the service, `[05:00, 05:55)`
returns nothing and `[05:00, 05:55:01)` returns it, so the adapter sends the
end plus one second.

Every issuance is returned, corrections included. SPC sometimes reissues an
outlook within one cycle; IEM marks the one it takes as canonical for each
issuance hour with that hour in `CYCLE`, 1, 6, 13, 16, or 20 for Day 1, and the
others with `-1`. The 01 UTC Day 1 outlook of 6 May 2024 was issued at 00:57 and
again at 01:39, and only the second carries cycle 1. IEM calls this assignment
"not an exact science". Filter on `CYCLE` for one outlook per cycle, or on
`PRODISS` for the latest issued before a moment.

An outlook that drew no area is still a row, with a null shape and empty
`THRESHOLD` and `CATEGORY`: the Day 4 to 8 outlooks issued at 08:58 on 6 May 2024
drew one area on Day 4 and none on Days 5 to 8. IEM's page says such outlooks
have no entries; they do. A window with no outlooks at all is answered with the
line `ERROR: no results found for your query` instead of a zip, and the adapter
writes a zip with no members for it.

## Why the bytes are rewritten

As with [`noaa:nws-warnings`](noaa-nws-warnings.md#why-the-bytes-are-rewritten),
each zip is built on request and stamped with the time it was built, so the
adapter writes a canonical zip: the same members, stored uncompressed and stamped
1980-01-01 00:00, with the DBF's last-update date set to 1980-01-01. Every
provenance sidecar records it ([ADR 0053](../adr/0053-iem-shapefile-archives.md)).
IEM corrects the archive in place: on 8 August 2025 it fixed the dates of Day 3+
outlooks before April 2019 that crossed a month boundary. A restore that finds
different rows fails its checksum.

## Sizes and limits

The service refuses more than ten outlook years in one request; the adapter asks
for a UTC month at a time. A year of Day 1 convective outlooks was 17 MB zipped
for 1987, when only categorical areas were drawn, and 40 MB for 2002. The
canonical files written are four to five times those sizes.

The same service serves WPC excessive rainfall outlooks (`type=E`). They are not
SPC products and are not part of this dataset.

Probes used to verify the endpoint and these behaviours:

```sh
U='https://mesonet.agron.iastate.edu/cgi-bin/request/gis/outlooks.py'
curl -o a.zip "$U?type=C&d=1&sts=2024-05-06T00:00Z&ets=2024-05-07T00:00Z"         # 92 rows, six issuances
curl -o b.zip "$U?type=C&d=1&sts=2024-05-06T05:00Z&ets=2024-05-06T06:00Z"         # the 05:55 issuance
curl "$U?type=C&d=1&sts=2024-05-06T12:00Z&ets=2024-05-06T12:01Z"                  # ERROR: no results found
curl -o c.zip "$U?type=C&sts=2024-05-06T00:00Z&ets=2024-05-06T13:00Z"             # Days 1 to 8, null shapes for 5 to 8
curl -o d.zip "$U?type=F&d=1&sts=2006-01-01T00:00Z&ets=2007-01-01T00:00Z"         # first fire outlook 2006-05-02
curl "$U?type=C&d=1&sts=1987-01-01T00:00Z&ets=2003-01-01T00:00Z"                  # refused: ten outlook years
```

IEM's JSON API returns one outlook as GeoJSON (`/api/1/nws/spc_outlook.geojson`),
named by its valid date, day, and cycle. It cannot be asked what was issued in a
span, and it returns only the canonical issuance of each cycle, so this dataset
reads the shapefile service.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Columns, cycle handling, geometry forms, and archive notes: IEM's
  [download page](https://mesonet.agron.iastate.edu/request/gis/outlooks.phtml).
- Parameters and the ten-year limit: the service's own help page, at the
  endpoint with `?help`.
- Coverage start and the Day 1 issuance hours: the probes above.
- Terms and license: IEM's [disclaimer](https://mesonet.agron.iastate.edu/disclaimer.php).
  The citation names SPC as the origin and IEM as the archive.
- Update frequency: IEM states none, and the entry says so; latency is empty for
  the same reason.
- No window limit is declared: the adapter splits any window into months and
  enforces none.

[NOAA access notes](noaa.md).

--8<-- "generated/catalog/noaa/spc-outlooks.md"
