# NGS emergency response imagery header fixtures

Each `.head` file is the first 1,024 bytes, unmodified, of one public-domain
GeoTIFF in NOAA's `noaa-eri-pds` bucket, read with an HTTP `Range: bytes=0-1023`
request on 2026-09-29 UTC. That prefix holds everything
`usdata.providers.noaa.geotiff` reads from these files: the first image file
directory and the pixel scale, tiepoint, and GeoKey values it points at. No
pixel data is included.

| File | Source key | Object size | ETag | SHA-256 of the prefix |
|---|---|---|---|---|
| `joplin-utm-tile.head` | `2011_Joplin_Tornado/may26JPEGtiles_UTMZone15/may26C372500e4100000n.tif` | 2,379,729 | `b666937e3e66935b662e47bb87ff54a4` | `bb4965a7a10504a67e71405496380f4023725c8722bcb8dae90912f28b5b29c6` |
| `helene-point-tile.head` | `2024_Hurricane_Helene/20240927a_RGB/20240927aC0852400w294245n.tif` | 1,977,776 | `bd6a8ff0911db2112adda3610d6adcdc` | `39e11d966663305a80df9f47569c52095fb625546f543c13d96c13a39ffe5076` |
| `debby-mosaic-bigtiff.head` | `2024_Hurricane_Debby/20240807a_RGB/20240807a_RGB.tif` | 29,549,276 | `c076743f96a599b1ffede63f2fc9f63e-4` | `8a1b47cca95c79280d4af890dc974301ee0192337cfb995368c1938b5ede7447` |

They cover the three georeferencing cases the adapter meets:

- The Joplin tile is a classic little-endian TIFF, 0.25 m pixels in UTM metres,
  with no GeoKey directory at all: the file states no coordinate system, and
  only its folder name, `UTMZone15`, gives the zone.
- The Helene tile is geographic (WGS 84) and registers its tiepoint to the
  centre of the first pixel (`RasterPixelIsPoint`), so its area starts half a
  pixel west and north of the tiepoint.
- The Debby flight mosaic is a BigTIFF in Web Mercator (EPSG:3857) with
  2.39 m pixels.
