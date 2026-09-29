# NWS damage surveys

`noaa:nws-damage-surveys`, available since v0.34, reads the National Weather
Service [Damage Assessment Toolkit](https://apps.dat.noaa.gov/StormDamage/DamageViewer/)
(DAT) through its public ArcGIS feature service, checked on 2026-09-29:

```
https://services.dat.noaa.gov/arcgis/rest/services/nws_damageassessmenttoolkit/DamageViewer/FeatureServer
```

After a tornado or a damaging wind event, NWS offices survey the damage and
enter it in the DAT. The service holds three layers, and a query reads one:

| `layer` | Layer | Features on 2026-09-29 | What one feature is |
|---|---|---|---|
| `points` | 0, Damage Points | 240,169 | One rated damage point: the damage indicator and degree of damage, an EF rating and wind estimate, often a photo |
| `lines` | 1, Damage Lines | 12,965 | One tornado track, with start and end times and positions, length, width, and rating |
| `polygons` | 2, Damage Polygons | 11,152 | One damage area, usually the extent of an EF rating along a track |

The service describes its data as preliminary: "While the data has been
quality controlled, it is still considered preliminary. Official statistics for
severe weather events can be found in the Storm Data publication." Storm Data
is [`noaa:storm-events`](noaa-storm-events.md); the SPC's database is
[`noaa:spc-tornado-reports`](noaa-spc-tornado.md). The photos attached to the
points are [`noaa:nws-damage-photos`](noaa-nws-damage-photos.md).

- `-p layer=points|lines|polygons` is required.
- Both timestamps are required, in UTC. The window selects by **storm time**,
  inclusive at both ends: `stormdate` on points and polygons, `starttime` on
  lines. See [storm times](#storm-times).
- A `bbox` or `location` is sent to the service as an envelope, and features
  intersecting it are returned. A county's box is a rectangle, so it can reach
  past the county.
- `-p office=TSA,OUN` keeps features surveyed by those offices. It works on
  points and lines; polygons record no office and refuse it. A track shared by
  offices lists them joined by commas (`JAN,MOB`) and matches each of them.
- `-p efscale=EF4,EF5` keeps those ratings. The toolkit writes `EF0` to `EF5`,
  `EF3+`, `EFU`, `UNKNOWN`, `N/A`, `TSTM/Wind` (straight-line wind), and
  `Tropical`; case does not matter in the parameter.
- `-p include_undated=true` adds the features with no storm time, which then
  match every window.
- `-p as_of=2026-09-29T00:00Z` reads the service as it stood at that instant.
  See [pinning a live service](#pinning-a-live-service).
- `variables` is rejected: the attributes are fixed. Free text is rejected as
  everywhere.

```sh
usdata fetch noaa:nws-damage-surveys --start 2011-04-27 --end 2011-04-28T12:00Z -p layer=lines
usdata fetch noaa:nws-damage-surveys --location "Osage County, OK" \
  --start 2024-05-06T12:00Z --end 2024-05-07T12:00Z -p layer=points -p efscale=EF3,EF4
usdata fetch noaa:nws-damage-surveys --start 2024-05-06T12:00Z --end 2024-05-07T12:00Z \
  -p layer=lines -p as_of=2024-05-08T00:00Z
```

## What arrives

GeoJSON, as the service writes it: one `FeatureCollection` per asset, WGS84
coordinates, every attribute of the layer under `properties`, and dates as
milliseconds since 1970 UTC. There is no bundled GeoJSON reader, so
`open()` refuses the file; `json.load` reads it, and `geopandas.read_file`
does too where it is installed. Sizes are not known before download.
Access was verified without credentials.

A layer serves at most 2000 features per request, so a query becomes one
asset per run of at most 2000 matching features: listing asks for every
matching object id, sorts them, and cuts them into runs, each asked for by its
first and last id, `...&where=<filters> AND objectid >= 2051923 AND objectid <=
2155170&orderByFields=objectid&f=geojson`. The asset id carries the run:
`nws_damage_lines_20240506_20240507_2051923-2155170_4361586bd656.geojson`.
The busiest three days of 2025, 14 to 16 March, hold 4,720 points and list as
three pages.

The service reports its own failures as HTTP 200 with an `error` body; a
fetched page holding one, or one the service cut short at its record limit, is
refused and leaves no file.

## Pinning a live service

The DAT is edited live. Surveys appear over days: the tracks for 6 May 2024
numbered 20 as of 8 May, 41 as of 12 May, 55 as of 1 June, and 58 now, and one
was still being added on 21 May. Features are revised, and some are deleted:
27 April 2011's points numbered 1,402 on 26 November 2020 and number 1,397 now.

Paging by object-id range keeps that from disturbing more than it must. An edit
changes only the page whose range holds the feature, and a feature added later
takes a new, higher id that falls past every listed range, so it appears when
the query is listed again rather than shifting the pages already pinned. A
pinned page whose feature was edited still fails its checksum on restore.

`as_of` removes the drift. The service archives every edit since 25 November
2020 and answers any request as of an instant (`historicMoment`), so a query
that names one lists and fetches exactly what the service held then, and a
restore months later gets the same bytes. A request as of a recent instant
returned the live page byte for byte. The instant is recorded in each asset's
`properties`. An instant before the archive begins is refused, because the
service answers it with nothing rather than an error; an instant in the future
is refused too, since its pages would change until it arrived. The live test
pins the Barnsdall EF4 track this way.

## Storm times

Times are UTC. The Barnsdall, Oklahoma EF4 of 6 May 2024 began at 9:12 PM CDT;
its track reads `starttime` 1715047920000, 02:12 UTC on 7 May, so a window over
an evening in the central U.S. crosses a UTC date.

- **Tracks** have both `stormdate` and `starttime`, equal wherever both are
  present. `starttime` is never empty, while one track, a 27 April 2011 EF4
  entered in June 2026, has no `stormdate`, so the window uses `starttime` on
  tracks. 81 tracks end before they start.
- **Undated features.** 41 points (40 of them surveyed in 2010 to 2012) and
  254 polygons have no `stormdate`. They are outside every window unless
  `include_undated=true`, which adds all of them, in the box and filters asked
  for, to any window.
- **Date-only stamps.** Many older points record only the date, stamped at
  00:00 UTC: 2,650 of 2011's 5,217, and more than 300 a year from 2011 to 2020,
  against a few dozen a year since 2021. 27 April 2011's points in Alabama read
  `2011-04-27T00:00Z` although the tornadoes struck that afternoon and evening,
  local time. For surveys before 2021, span whole UTC days, and reach back to
  00:00 UTC on the local date of the storm.
- **Placeholders.** Eleven points surveyed in 2013 to 2016 carry
  `1970-01-01T00:00Z`, the epoch, as their storm time.
- **Historical reconstructions.** Offices have entered surveys of past
  tornadoes: the Des Plaines, Illinois tornado of 22 May 1855, the Rockford
  tornado of 1928, the 1965 Palm Sunday and 1974 Super Outbreak tornadoes, and
  others. The earliest storm time is 1855-05-22T23:59:24Z. The layers'
  metadata advertises a time extent reaching back to the second century and
  forward to 2029, which the data do not bear out; statistics over `stormdate`
  give the real range, and the catalog uses it. Surveys become numerous in
  2010.

## Attributes

The layers do not share a schema. Points have `office`, `damage` and
`damage_txt` (the EF-scale damage indicator), `dod` and `dod_txt` (its degree of
damage), `windspeed` as text, `injuries`, `deaths`, `lat`, `lon`, `image` (the
file name of a photo, often empty), and `surveydate`. Lines have `wfo`,
`starttime`, `endtime`, start and end coordinates, `length`, `width`,
`injuries`, `fatalities`, `efnum` (`-99` unknown), `maxwind`, and damage
estimates. Polygons have `length`, `width`, `injuries`, and `fatalities`, and
no office. All three have `objectid`, `globalid`, `event_id` (an office's own
label, empty on most points), `efscale`, `comments`, and edit stamps.

The service states no units. The lengths and widths read as miles and yards:
the Barnsdall track's `length` 40.8 and `width` 1700. The `office` on points is
not always clean: 384 are null, 7 empty, and a few mistyped (`meg`, `OAXx`),
which is why the office filter compares upper case. `efscale` on points also
holds a handful of junk values (`Scripts disabled`, `Correction`); the
parameter accepts only the ratings above.

## Probes

Checked on 2026-09-29.

```sh
B='https://services.dat.noaa.gov/arcgis/rest/services/nws_damageassessmenttoolkit/DamageViewer/FeatureServer'
curl "$B/1?f=json"                      # maxRecordCount 2000, archivingInfo from 1606331043000
curl -G "$B/0/query" --data-urlencode 'where=1=1' -d returnCountOnly=true -d f=json    # 240169
curl -G "$B/0/query" --data-urlencode 'where=stormdate IS NULL' -d returnCountOnly=true -d f=json   # 41
curl -G "$B/1/query" --data-urlencode "where=starttime >= TIMESTAMP '2024-05-06 12:00:00' AND starttime <= TIMESTAMP '2024-05-07 12:00:00'" \
  -d returnCountOnly=true -d f=json                                                   # 58
curl -G "$B/1/query" --data-urlencode "where=starttime >= TIMESTAMP '2024-05-06 12:00:00' AND starttime <= TIMESTAMP '2024-05-07 12:00:00'" \
  -d returnCountOnly=true -d historicMoment=1715126400000 -d f=json                   # 20, as of 8 May 2024
curl -G "$B/0/query" --data-urlencode "where=stormdate >= TIMESTAMP '2011-04-27 00:00:00' AND stormdate <= TIMESTAMP '2011-04-28 12:00:00'" \
  -d returnCountOnly=true -d historicMoment=1606262400000 -d f=json                   # 0: before the archive
curl -G "$B/0/query" --data-urlencode "where=stormdate >= TIMESTAMP '2025-03-14 00:00:00' AND stormdate <= TIMESTAMP '2025-03-17 00:00:00'" \
  -d outFields=objectid -d f=geojson                                                  # 2000 features, exceededTransferLimit
```

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms,
variables, and extent comes from one of these. A field the agency does not
publish is left empty rather than estimated.

- What the DAT is, and how data reach the public service ("Once
  quality-controlled, the data becomes available externally via a public web
  portal, as well as public Geographic Information System (GIS) services"):
  NWS [Service Change Notice 22-84](https://www.weather.gov/media/notification/pdf2/scn22-84_damage_assessment_toolkit.pdf),
  which put the public portal into operation on or after 26 October 2022. The
  Product Description Document it links returned 404 on 2026-09-29.
- The preliminary-data statement and the layers, fields, record limit, archive
  start, and time reference (UTC): the [feature service](https://services.dat.noaa.gov/arcgis/rest/services/nws_damageassessmenttoolkit/DamageViewer/FeatureServer)
  and its layers' `?f=json` descriptions.
- Temporal extent, counts, null and placeholder dates, and attribute values:
  statistics queries against the service on 2026-09-29, as in the probes above.
- Terms and license: the NWS [disclaimer](https://www.weather.gov/disclaimer),
  "The information on National Weather Service (NWS) Web pages are in the
  public domain, unless specifically noted otherwise". The service's
  `copyrightText` is "NOAA National Weather Service".
- Citation: the DAT publishes no citation form, so the entry uses the agency,
  product, and service.
- Latency is empty: the NWS states none, and surveys appear as offices finish
  them, days to weeks after a storm.
- No window limit is declared, because the adapter enforces none; listing
  every point ever surveyed takes one id request and makes 121 pages.

[NOAA access notes](noaa.md).

--8<-- "generated/catalog/noaa/nws-damage-surveys.md"
