# NGS emergency response imagery

Available since v0.34 as `noaa:emergency-response-imagery`. After a hurricane,
flood, fire, or tornado, NOAA's National Geodetic Survey (NGS) flies the damaged
area, mosaics the photographs, and cuts the mosaic into GeoTIFF tiles, which it
shows at [storms.ngs.noaa.gov](https://storms.ngs.noaa.gov/) and publishes in
the anonymous `noaa-eri-pds` S3 bucket through NOAA Open Data Dissemination.
The bucket also holds yearly pre-event surveys of the coasts. No AWS
credentials or SDK are needed.

## Events

The bucket's top level is one folder per event, 52 when listed on 2026-09-29,
from `2005_Hurricane_Katrina` to `2026_Pre_Event`. Name one exactly with
`event`; a misspelling is answered with the nearest names and the full list.

**Only three events are tornadoes**: `2011_Joplin_Tornado` (61 tiles, 2.1 GB),
`2015_Illinois_Tornadoes` (171 tiles, 9.2 GB), and `2020_Nashville_Tornado`
(163 tiles, 7.1 GB). NGS's site also lists a 2011 Tuscaloosa tornado response
that is not in the bucket. The rest are 36 hurricanes and tropical storms,
five floods (`2015_Midwest_Flood`, `2016_Louisiana_Flooding`, `2025_Texas_Flood`,
and the Midwest floods of 2025 and 2026), `2023_California` and
`2025_California_Fires`, the 2009 Nor'easter, and five pre-event surveys, 2022
to 2026. Events
run from 2.1 GB (Joplin) to 2.7 TB of GeoTIFFs (Helene).

## Selection

- `event` (required): the event folder.
- `collection`: one or more folders under the event, comma-separated, such as a
  flight, `20200307a_RGB`, or a nested folder, `20221112a_RGB/ortho-cogs`.
  Without it, every folder is selected. A folder that does not exist is
  answered with the event's folders.
- `max_gb` (default 25): a selection whose listed sizes add up to more than
  this many gigabytes (10^9 bytes) is refused, with its file count, total, and
  largest folders, so a dry run of a whole hurricane says where its terabytes
  are. Raise it deliberately.
- A **bbox** or place keeps the files whose footprint meets it (see below).
- `start`/`end`, `variables`, and free text are refused.

Every `.tif` in a selected folder is one asset, fetched whole and unchanged. The
`raw/` folders beside recent flights (the individual camera JPEGs and their
`.geom` files) and each event's `downloads/` folder (tar archives per flight,
up to 126 GB) are not part of the dataset, and neither are the VRT, shapefile,
MRF, and FlatGeobuf indexes. Asset ids are the whole bucket key, since two
folders can hold files of the same name. Listing walks one folder at a time,
so the thousands of raw frames are never listed.

## Folders and file names

| Naming | Where | What the name states |
|---|---|---|
| `20200307aC0852700w360900n.tif` | 2005 to 2026, most folders | North-west corner: 85°27'00"W 36°09'00"N. Older folders drop the flight prefix or the `C` (`0771630w353730n.tif`, `nov06b0740600w394930n.tif`); pre-event tiles prefix the survey (`EC2301a_OB_N_C0741545w393044n.tif`). |
| `may24C350000e4102500n.tif` | Joplin and Irene, 2011 | North-west corner in UTM metres, zone from the folder: `may24JPEGtiles_UTMZone15`. |
| `nov15C377500e4087500n.tif` | 2009 Nor'easter | UTM metres with no zone anywhere. |
| `29907494.tif`, `geo-C24700126.tif`, `S18367842.tif`, `2016obP28168649.tif`, `20200918bRR26261021.tif`, `061922_1112221943103_057_RGB1.tif`, `mwflood-28-98.tif` | Wilma, Ernesto, Humberto, Gustav, Ike, Arthur, the Matthew and Louisiana obliques, Sally's NIR frames, Nicole's `ortho-cogs`, one Midwest-flood flight | Nothing: individual frames or row and column numbers. |
| `20240807a_RGB.tif` | Recent flights (Debby, Francine, Milton, Erin, the 2025 floods, 2024 pre-event) | A reduced-resolution mosaic of the whole flight, beside its tiles. |

Degree tiles are 90 arc-seconds on a side through 2020 and 45 arc-seconds from
2021, each with a 0.0001° buffer; UTM tiles are 2.5 km with a buffer of up to
50 m. Folder names begin with the flight's local date where they carry one
(`20200307a`, `aug30`, with the event's year).

## Footprints and bbox

With a bbox, each tile is placed by the corner its name states and the tile
size of its folder, read from the GeoTIFF header of the folder's first tile in
one 64 KiB range request. The box is widened by 2 arc-seconds (about 60 m) for
degree names, since some names truncate a second (`3044` for 30'45"), and by
100 m for UTM names, so a tile that touches the box is never missed and one
within that distance of it may be kept. A flight mosaic is placed by its own
header. Each asset's `bbox` is that footprint. See
[ADR 0052](../adr/0052-eri-footprints-from-tile-names.md).

A bbox is **refused**, not ignored, when a selected folder holds any file whose
name places nothing: the numbered, oblique, and single frames above, and the
Nor'easter's zone-less UTM tiles. The error names those folders and the ones
that can be placed; pass the latter with `collection`. Without a bbox these
events list like any other. Positions are only as good as NGS states them:
3 to 5 m horizontally in flat terrain, not assessed.

## Time

`start` and `end` are refused. Folder dates are local calendar dates (the raw
frames of the Texas flood's `20250710a` flight are stamped 00:00 to 01:59 UTC on
11 July), and the 2005 to 2008 frames, the 2009 finals, and the pre-event
surveys carry no date. Choose flights by folder instead. An asset's `time` is
its folder's local day as the UTC interval it covers in U.S. time zones, from
04:00 UTC that day to 10:00 UTC the next, or, for an undated folder, an interval
open from 1 January of the event's year.

## The files

GeoTIFFs of 8-bit red, green, and blue, with a fourth transparency band in the
2017 to 2019 tiles and from 2021, in NAD83 or WGS 84 degrees, or UTM metres for
2009 to 2011. Three tiles of every folder that can be placed, probed on
2026-09-29, were JPEG-compressed through 2020, LZW-compressed after events from
2021, and Deflate-compressed in the pre-event surveys. NODD describes the files
as GeoTIFF, cloud-optimized for recent events, and every file probed carried
internal overviews. Sizes range from 0.15 MB (a pre-event tile of mostly empty
sea) to 1.7 GB (a 2025 California fires tile). The UTM tiles state no coordinate system at all, so
their assets record `properties: {utm_zone: "15"}`, taken from the folder name.

No reader is bundled; the files are bytes. GDAL and rasterio read them fully.
Pillow, which matplotlib installs, read the overviews of the JPEG and Deflate
tiles tried by seeking to a later image, which is enough to look at one; see the
[walkthrough](https://usdata.dev/datasets/noaa/emergency-response-imagery/).

## Examples

```sh
# The whole Nashville tornado flight: 163 tiles, 7.1 GB, listed only.
uv run usdata fetch noaa:emergency-response-imagery -p event=2020_Nashville_Tornado --dry-run

# The four tiles around the North Nashville and Germantown damage path.
uv run usdata fetch noaa:emergency-response-imagery -p event=2020_Nashville_Tornado \
  --bbox -86.80,36.165,-86.78,36.18

# Hurricane Matthew's oblique folders refuse a bbox, so name tiled flights:
# one tile from each, 17 MB, in eastern North Carolina.
uv run usdata fetch noaa:emergency-response-imagery -p event=2016_Hurricane_Matthew \
  -p collection=20161011_RGB_JpegTiles_GCS_NAD83,20161013_RGB_JpegTiles_GCS_NAD83 \
  --bbox -77.62,35.93,-77.61,35.94 --dry-run
```

See the [service research notes](noaa-services.md#ngs-emergency-response-imagery)
for dated upstream probes.

## Metadata sources

Every value in the catalog entry comes from one of these pages or from the
bucket itself; a field NGS does not publish is left empty rather than estimated.

- Description, update frequency, license, and terms: the [NODD registry
  entry](https://registry.opendata.aws/noaa-eri/) (its source,
  [`noaa-eri.yaml`](https://github.com/awslabs/open-data-registry/blob/main/datasets/noaa-eri.yaml),
  gives "Manually when needed" and the NODD open-use statement) and the [NOAA Open
  Data Dissemination](https://www.noaa.gov/information-technology/open-data-dissemination)
  page.
- Spatial resolution: each event's page on [storms.ngs.noaa.gov](https://storms.ngs.noaa.gov/)
  states an approximate ground sample distance: 35 cm (1.14 feet) for
  [Katrina](https://geodesy.noaa.gov/storm_archive/storms/katrina/index.html)
  and [Joplin](https://geodesy.noaa.gov/storm_archive/storms/joplin/index.html),
  ~15 cm for [Nashville](https://storms.ngs.noaa.gov/storms/nashville/index.html),
  and 15 - 30 cm for [Helene](https://storms.ngs.noaa.gov/storms/helene/index.html).
- Temporal resolution, accuracy, and constraints: the per-event InPort records,
  such as [Nashville's](https://www.fisheries.noaa.gov/inport/item/59027) (one
  flight on 2020-03-07, 3 to 5 m horizontal accuracy "not assessed", "not
  intended for mapping, charting or navigation").
- Citation: NGS publishes a citation per event in InPort, such as "National
  Geodetic Survey, 2026: 2020 NOAA NGS Emergency Response Imagery: Nashville,
  TN Tornado, https://www.fisheries.noaa.gov/inport/item/59027"; none covers the
  whole bucket, so the entry uses the agency, product, and access form. Cite the
  event's record where one exists.
- Spatial and temporal extent, variables, and file facts: the bucket listing of
  2026-09-29 and the GeoTIFF headers probed that day (see the research notes).
  The extent covers every tile corner, 124.8°W to 64.5°W and 17.6°N to 48.5°N;
  the start is Katrina's first flight folder, `aug30`, of 2005.
- Latency is empty: NGS states none.

[All NOAA datasets](noaa.md).

--8<-- "generated/catalog/noaa/emergency-response-imagery.md"
