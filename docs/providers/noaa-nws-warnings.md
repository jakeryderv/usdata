# NWS watch, warning, and advisory geometries

`noaa:nws-warnings`, available since v0.35.0, uses the
[Iowa Environmental Mesonet](https://mesonet.agron.iastate.edu/request/gis/watchwarn.phtml)
archive of National Weather Service products, at
`https://mesonet.agron.iastate.edu/cgi-bin/request/gis/watchwarn.py`, checked on
2026-10-08. IEM is part of Iowa State University and is not an NWS endpoint; it
is the maintained archive, because the official `api.weather.gov/alerts` keeps
none.

Each fetched file is a zip holding a shapefile (`.shp`, `.shx`, `.dbf`, `.prj`,
`.cpg`) and a CSV of the same attributes. One row is one VTEC event with one
geometry, and the `GTYPE` column says which kind:

| `GTYPE` | Geometry | From |
|---|---|---|
| `P` | The storm-based warning polygon the forecaster drew | 1 January 2002 |
| `C` | The outline of one county, parish, or forecast zone the product was issued for, named by `NWS_UGC` | 1986 for tornado, severe thunderstorm, flash flood, and marine warnings; 12 November 2005 for the rest |

A storm-based warning appears both ways: once as its polygon and once per county
it was issued for. Watches, advisories, and zone-based warnings are `C` rows
only. For one evening, 6 May 00Z to 7 May 12Z 2024, the archive holds 3,563 rows,
among them 466 county rows of tornado watches (`TO.A`), 100 tornado warning
polygons (`TO.W`, `P`) and the 224 counties they named, and heat, wind, fire, and
flood products besides.

- Both timestamps are required, in UTC, to the second. The window selects rows
  by `ISSUED`, inclusive at both ends. See
  [what the window selects](#what-the-window-selects).
- A window is fetched as one zip per UTC month it touches; nothing is requested
  while listing, and sizes are not known before download.
- A place is a state: `--location Oklahoma` sends IEM's state filter.
  `-p wfo=OUN,TSA` names issuing offices instead. A county is refused, naming
  [`noaa:nws-vtec-events`](noaa-nws-vtec-events.md), which reads one county's
  events. A `bbox` or `lat`/`lon` is refused: the service filters by state or
  office, not by box.
- `-p events=TO.W,SV.W,TO.A` narrows to VTEC phenomena and significance pairs.
- `-p storm_based=true` keeps only the `P` rows.
- `-p followups=true` adds the polygons of follow-up statements (SVS) issued
  after a warning, each its own row; by default only the issuance polygon is
  returned, with its impact tags.
- `variables` is rejected: the columns are fixed. Free text is rejected as
  everywhere.
- There is no bundled shapefile reader, so `open()` refuses the zip.
  `geopandas.read_file(path)` reads it directly, and so does pyshp's
  `shapefile.Reader(path)`. The CSV inside needs nothing but pandas, and names
  the same columns in full, such as `PRODUCT_ID` for the DBF's `PROD_ID`.
  Timestamps are `YYYYMMDDHHMM` strings in UTC in the DBF and
  `YYYY-MM-DD HH:MM` in the CSV.

```sh
usdata fetch noaa:nws-warnings --start 2024-05-06T18:00Z --end 2024-05-07T12:00Z -p events=TO.W,TO.A
usdata fetch noaa:nws-warnings --location Oklahoma --start 2024-05-01 --end 2024-05-31 -p storm_based=true
```

## What the window selects

IEM's documentation says the start and end "determine which events to include"
without naming a column. Probing shows it is `ISSUED`, the event's start as
last updated, and that the end is exclusive to the minute:

- Every row of an unnarrowed request has `ISSUED` inside the window; 466 of the
  3,563 rows above have `INIT_ISS`, the time of the product that started the
  event, before it. Those are mostly advisories and flood warnings sent the
  previous day to begin at a later hour.
- `[03:00, 03:27)` UTC on 7 May returns 131 rows issued up to 03:26, and
  `[03:00, 03:28)` returns 136, adding the five issued at 03:27. The adapter
  sends the end plus one second, so a row issued at exactly the requested end
  minute is returned.
- A Tornado Watch issued at 19:05 UTC on 6 May and running to 03:48 the next
  morning is not returned for a window inside it. The window asks what was
  issued, not what was in effect, as for
  [`noaa:nws-vtec-events`](noaa-nws-vtec-events.md#issued-not-in-effect).

For tornado and severe thunderstorm warnings `ISSUED` and `INIT_ISS` are the same
instant. For a product that starts in the future they are not: IEM's
[FAQ](https://mesonet.agron.iastate.edu/info/datasets/vtec.html) gives a Winter
Storm Watch sent at 17:00 UTC on 19 March 2019 to begin at 23:00 the next day,
and recommends `INIT_ISS` as the time the public knew of it. A window meant to
hold only what was known before some moment should therefore end at that moment
and then filter on `INIT_ISS` locally.

The service also offers "events valid at" one instant (`timeopt=2`); the adapter
does not expose it, since a usdata window is a span. Widen the window backwards
and compare `INIT_ISS` and `EXPIRED` with the instant yourself.

## Why the bytes are rewritten

The zip is built on request. Two identical requests seconds apart return
different bytes: each member is stamped with the time the zip was built, and the
DBF header with the date, while every member's content is otherwise identical.
A lockfile could not pin such an answer, so the adapter writes a canonical zip:
the same members in the same order, each stored uncompressed and stamped
1980-01-01 00:00 with no extra fields, and the DBF's last-update date set to
1980-01-01. Storing rather than deflating keeps the bytes the same whichever
zlib a machine has; the file is four to five times the size of IEM's
(1.8 MB zipped became 8.3 MB for the example evening). Every
provenance sidecar records the rewrite under `transformations`
([ADR 0053](../adr/0053-iem-shapefile-archives.md)).

The archive itself changes too: rows are the latest state of each event, so an
event still running when fetched can change later, and IEM has reprocessed the
archive before, such as removing the polygons of cancelled segments on
10 April 2024. A restore that finds different rows fails its checksum rather
than returning them silently.

## Sizes and limits

Without a state or office the service caps a request at one year. The adapter
asks for a UTC month at a time, so the cap is never reached. IEM's pregenerated
yearly files give a sense of size: every product for 2024 is 335 MB zipped, the
tornado, severe thunderstorm, marine, and flash flood warnings 45 MB, and their
storm-based polygons 6.2 MB, and the canonical files written are four to five
times those sizes. Narrow with `events` or `storm_based` for long windows.

Probes used to verify the endpoint and these behaviours:

```sh
U='https://mesonet.agron.iastate.edu/cgi-bin/request/gis/watchwarn.py'
curl -o a.zip "$U?accept=shapefile&sts=2024-05-06T00:00Z&ets=2024-05-07T12:00Z"   # 3,563 rows
curl "$U?accept=csv&sts=2024-05-07T03:00Z&ets=2024-05-07T03:27Z"                   # 131 rows, to 03:26
curl "$U?accept=csv&sts=2024-05-07T03:00Z&ets=2024-05-07T03:28Z"                   # 136 rows, to 03:27
curl "$U?accept=csv&sts=2024-05-07T03:00Z&ets=2024-05-07T03:30Z&limit1=1"          # 19 rows, all GTYPE P
curl "$U?accept=csv&sts=2024-05-07T03:00Z&ets=2024-05-07T03:30Z&addsvs=1"          # 163 rows, 46 P
curl "$U?accept=geojson&sts=2024-05-06T00:00Z&ets=2024-05-06T03:00Z"               # 422: no GeoJSON
```

IEM's JSON API has a GeoJSON service for warning polygons,
`/api/1/vtec/sbw_interval.geojson`, but it holds storm-based polygons only: no
watches, no advisories, and no county or zone rows. This dataset reads the
shapefile service because it is the whole archive.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Coverage dates, the one-year download limit, and the pregenerated file sizes:
  IEM's [download page](https://mesonet.agron.iastate.edu/request/gis/watchwarn.phtml).
- Column meanings and units: the DBF schema in IEM's
  [VTEC FAQ](https://mesonet.agron.iastate.edu/info/datasets/vtec.html), which
  gives wind tags in MPH, hail tags in inches, and areas computed in an Albers
  projection.
- Parameters: the service's own help page, at the endpoint with `?help`.
- Terms and license: IEM's [disclaimer](https://mesonet.agron.iastate.edu/disclaimer.php),
  which places its materials in the public domain and says attribution "would
  be appreciated". The citation names NWS as the origin and IEM as the archive.
- Update frequency: IEM states none, and the entry says so; latency is empty for
  the same reason.
- No window limit is declared: the adapter splits any window into months and
  enforces none.

[NOAA access notes](noaa.md).

--8<-- "generated/catalog/noaa/nws-warnings.md"
