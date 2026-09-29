# 0052: Emergency response imagery is placed by tile names and one header per folder, and refuses a bbox where names place nothing

Status: accepted. Date: 2026-09-29.

## Context

NOAA's National Geodetic Survey publishes its post-event aerial imagery in the
public `noaa-eri-pds` bucket: 52 event folders, each holding folders (mostly one
per flight) of GeoTIFFs, 834,087 objects and about 39 TB when listed on
2026-09-29, of which 268,231 are GeoTIFFs. The bucket publishes no footprint for
a file. A spatial query needs one, and there are three ways to get it.

1. **Every file's own header.** Exact, and one byte-range request per file:
   9,576 requests to answer one bbox over Hurricane Helene.
2. **The per-flight index files.** Flights since 2020 carry a GDAL VRT and a
   tile-index shapefile; earlier ones carry nothing, and a README in one Helene
   flight warns that its index lists eight tiles the flight does not hold.
3. **The file names.** Most tiles are named for a corner:
   `20200307aC0852700w360900n.tif` is 85°27'00"W 36°09'00"N, and
   `may24C350000e4102500n.tif`, in `may24JPEGtiles_UTMZone15`, is 350,000 m E
   4,102,500 m N in UTM zone 15.

Probes of the whole listing and of tile headers established what the names say
and what they do not:

- Every name encodes the tile's **north-west corner**. Degree tiles carry a
  0.0001° buffer past it; some names truncate a second (`3044` for 30'45"), so
  the true corner can lie up to 1" beyond the name. UTM tiles carry a buffer of
  1.75 to 50 m, which varies within a folder.
- **Tile size is not in the name and varies by folder**: 90" (0.0252° with the
  buffer) through 2020, 45" (0.0127°) from 2021, and 2,504 to 2,600.15 m for
  the UTM tiles. Checking three tiles in each of the 315 folders that can be
  placed found the size uniform within every folder, and every sampled tile's
  header within the tolerances below of its name.
- **The UTM GeoTIFFs state no coordinate system**: they have no GeoKey
  directory. Only the folder name gives the zone, and the four 2009 Nor'easter
  folders (`nov15_images`, `Final_C1_images`) give none.
- Several events hold files whose names state no position at all: numbered
  frames (2005 to 2008), obliques (2014, 2016), near-infrared frames (2020
  Sally), orthorectified single frames (2022 Nicole), and row-and-column names
  (2015 Midwest flood). Recent flights also hold one reduced-resolution mosaic
  named after the folder, `20240807a_RGB.tif`, in degrees or Web Mercator.

## Decision

A tile's footprint is its name's corner extended by the size of its folder's
tiles, which is read from the georeferencing of **one tile per folder**, the
first by key, in one 64 KiB byte-range request. The box is widened by 2" for
degree names, covering the truncated second and the buffer, and by 100 m for
UTM names; a tile within that distance of a query box is kept. The sampled
header must place its tile within the same tolerance of its name, or the query
fails. A folder's mosaic is placed by its own header. The footprint becomes the
asset's `bbox`.

UTM names are read only in a folder naming its zone, `UTMZone<n>`, northern
hemisphere, and every asset in such a folder records `utm_zone` in its
`properties`, since the file does not state it
([ADR 0043](0043-asset-properties.md)).

Where any selected folder holds a file whose name places nothing, a bbox is
**refused** with a `QueryError` that names those folders and the folders that
can be placed, rather than returning the unplaced files, dropping them, or
reading every one of their headers. The same event lists normally without a
bbox. Because only this can be known after listing, the refusal is not made by
`Provider.reject`, and the registry declares `spatial_subset: true`: a bbox
narrows what every placeable folder returns.

Headers are read with a small parser of the TIFF image file directory in
`usdata.providers.noaa.geotiff`, reading classic TIFF and BigTIFF in either byte
order, and UTM is converted with Krüger's series in
`usdata.providers.noaa.utm`, which agrees with PROJ to under a millimetre. Core
gains no dependency.

## Alternatives

- **A fixed tile size per naming scheme.** The listing alone cannot tell a 45"
  folder from a 90" one, and truncated names break a grid inferred from the
  spacing between names. The largest size everywhere would return a ring of
  neighbouring tiles, up to 1 GB each, around every box in the newer events.
- **The VRT or shapefile indexes.** They cover only flights since 2020, need a
  shapefile or XML reader for data the names already hold, and are known to
  disagree with the listing.
- **Reading every header.** Exact, but thousands of requests per query, and
  still no answer for the UTM tiles, whose headers state no zone.
- **Guessing the Nor'easter zone.** Its coordinates fit zone 18 near Norfolk,
  Virginia, but nothing published says so.
- **Dropping unplaceable files from a bbox query.** Silent: a caller could not
  tell a frame that missed the box from one that was never examined.
- **Selecting by flight date.** Folder dates are local calendar dates: the raw
  frames of the Texas flood flight `20250710a` are stamped 00:00 to 01:59 UTC
  on 11 July. The 2005 to 2008 frames and the pre-event surveys carry no date at
  all, so a window is refused and folders are chosen by name; an asset's `time`
  is its folder's local day as the UTC interval it covers from UTC-4 to UTC-10,
  or an interval open from the event's year.

## Consequences

A bbox query costs one listing per folder plus one small header read per
folder (and per mosaic): 5.5 seconds for a box over Asheville in all of
Helene's 20 flights, half a second for Nashville. Selection is conservative by
at most 2" (about 60 m) or 100 m: a tile that nearly touches the box is fetched,
and one that touches it is never missed. The rule rests on one tile size per
folder, which held in every folder probed. If NGS ever mixes tile sizes in a
folder, the sampled header will not describe its siblings and a larger tile
could be missed; the check of the sampled header against its name would not
notice, and only probing the folder's headers again would.
