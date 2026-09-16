# MRMS gridded radar products

Available since v0.15.0 as `noaa:mrms`. Multi-Radar Multi-Sensor merges every
NEXRAD radar with other sensors onto one fixed CONUS grid every two minutes.
Files are gzipped GRIB2 in the anonymous `noaa-mrms-pds` bucket, laid out as
`CONUS/<PRODUCT>/<YYYYMMDD>/MRMS_<PRODUCT>_<YYYYMMDD>-<HHMMSS>.grib2.gz`. No AWS
credentials or SDK are needed.

Require `product` and both timestamps. `product` is the exact directory name
from the table below, matched case-sensitively; a near-miss in case is
rejected with the intended name. Unknown parameters, text/geographic
constraints, and `variables` are rejected: each file is one whole CONUS grid
that the server cannot crop, and the product is the variable. Only the CONUS
domain is served; the bucket's ALASKA, CARIB, GUAM, and HAWAII domains, its
5 km CONUS grids, and its ProbSevere feeds are out of scope.

The adapter lists one `CONUS/<PRODUCT>/<YYYYMMDD>/` prefix per touched day,
follows S3 continuation tokens, and selects files whose stamps fall in the
inclusive UTC query interval. A query spans at most one day: a day of one
product is 720 files and, for reflectivity, more than a gigabyte. Split longer
intervals, and prefer the minutes around an event. Use `--dry-run` to see the
count and total size before downloading. Stamps are usually on even minutes,
but many products carry the merge second (`-200039`), so select by window
rather than by an exact stamp. The archive begins on 2020-10-14; earlier
windows are rejected before any request.

For example, fetch the one rotation-track file stamped 20:00:00 UTC on
2024-05-06 (about 95 kB):

```sh
uv run usdata fetch noaa:mrms -p product=RotationTrackML30min_00.50 \
  --start 2024-05-06T20:00:00Z --end 2024-05-06T20:00:00Z
```

## Supported products

Sizes are the range observed across 2024-05-06, a day with severe weather over
the Plains; quiet days are smaller. Grids are 0.01° (3,500 × 7,000 points)
except the rotation tracks, which are 0.005° (7,000 × 14,000 points).

| Product | Meaning | Units | File size | Day |
|---|---|---|---|---|
| `RotationTrack30min_00.50` | 30-minute maximum low-level azimuthal shear | 0.001 s⁻¹ | 131–445 kB | 179 MB |
| `RotationTrack60min_00.50` | 60-minute maximum low-level azimuthal shear | 0.001 s⁻¹ | 206–615 kB | 260 MB |
| `RotationTrack120min_00.50` | 2-hour maximum low-level azimuthal shear, hourly files | 0.001 s⁻¹ | 328–867 kB | 25 MB |
| `RotationTrackML30min_00.50` | 30-minute maximum mid-level azimuthal shear | 0.001 s⁻¹ | 35–174 kB | 52 MB |
| `RotationTrackML60min_00.50` | 60-minute maximum mid-level azimuthal shear | 0.001 s⁻¹ | 57–265 kB | 81 MB |
| `RotationTrackML120min_00.50` | 2-hour maximum mid-level azimuthal shear, hourly files | 0.001 s⁻¹ | 102–405 kB | 8 MB |
| `MergedReflectivityQCComposite_00.50` | quality-controlled composite reflectivity | dBZ | 1.5–2.4 MB | 1.3 GB |
| `MergedReflectivityComposite_00.50` | composite reflectivity without quality control | dBZ | 7.2–9.8 MB | 5.8 GB |
| `ReflectivityAtLowestAltitude_00.50` | reflectivity at the lowest altitude with data | dBZ | 1.1–1.7 MB | 925 MB |
| `MergedBaseReflectivityQC_00.50` | quality-controlled base reflectivity | dBZ | 1.1–1.9 MB | 1.0 GB |
| `MESH_00.50` | maximum estimated size of hail | mm | 32–60 kB | 28 MB |
| `MESH_Max_30min_00.50` | 30-minute maximum estimated hail size | mm | 36–106 kB | 40 MB |
| `MESH_Max_60min_00.50` | 60-minute maximum estimated hail size | mm | 41–146 kB | 50 MB |
| `VIL_00.50` | vertically integrated liquid | kg m⁻² | 440–857 kB | 444 MB |
| `VIL_Density_00.50` | vertically integrated liquid density | g m⁻³ | 209–355 kB | 185 MB |
| `EchoTop_18_00.50` | 18 dBZ echo top height | km | 773 kB–1.6 MB | 719 MB |
| `EchoTop_30_00.50` | 30 dBZ echo top height | km | 199–550 kB | 191 MB |
| `EchoTop_50_00.50` | 50 dBZ echo top height | km | 37–59 kB | 30 MB |
| `PrecipRate_00.00` | radar precipitation rate | mm h⁻¹ | 679 kB–1.1 MB | 564 MB |
| `LightningProbabilityNext30minGrid_scale_1` | probability of lightning in the next 30 minutes | % | 19–57 kB | 21 MB |

Rotation tracks accumulate the maximum azimuthal shear over the trailing
window, so a 30-minute file at 20:30 covers 20:00 to 20:30; the `ML` variants
use the 3–6 km mid-level layer that tornado research usually pairs with the
low-level track. The `00.50` and `00.00` suffixes are the product's nominal
height in kilometres, part of the directory name. The bucket holds about 240
CONUS product directories; extending the allowlist is a follow-up once a use
case needs another product.

## Reading grids

Files are opened with the `grib` extra, added in v0.15.0 with
`reader="grib2"`; see [readers and their limits](../reference/readers.md).
ecCodes has no parameter tables for MRMS's local GRIB discipline, so the reader
names the data variable from the product segment of the asset id, which is why
asset ids keep the exact upstream filename. Values are stored with the source's
sentinels: `-999` marks no coverage and `-99` marks no data within coverage in
the files probed, and neither is a GRIB missing value, so mask them yourself
before taking statistics. Files are gzipped; the reader decompresses in memory
and the cached bytes stay as published. Without the extra, use
`fetched.path` with any GRIB2 decoder after decompressing.

--8<-- "_snippets/large-grids.md"

## Archive coverage

Listing the product directories with a `/` delimiter found the first day
`20201014` for rotation tracks, composite reflectivity, and MESH; the catalog's
start records that day. Not every product has every two-minute file: on
2024-05-06, `MergedBaseReflectivityQC_00.50` and `PrecipRate_00.00` each had
719 files and the 2-hour rotation tracks are written hourly. The
[NODD registry](https://registry.opendata.aws/noaa-mrms-pds/) documents public
cloud access and the
[MRMS product guide](https://www.nssl.noaa.gov/projects/mrms/operational/tables.php)
describes each product's algorithm, units, and grid.

See the [service research notes](noaa-services.md#mrms-gridded-radar-products)
for dated upstream probes.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Updates, citation, and terms: the [NODD registry
  entry](https://registry.opendata.aws/noaa-mrms-pds/) ("Data is delivered in real-time
  with a 2-minute update cycle") and the [NOAA Open Data
  Dissemination](https://www.noaa.gov/information-technology/open-data-dissemination)
  statement it quotes.
- Resolution and variables: the [MRMS product
  guide](https://www.nssl.noaa.gov/projects/mrms/operational/tables.php) and the product
  table above; the registry lists exactly the products this adapter supports, with their
  units.
- Longest query window: `MAX_WINDOW` in `usdata.providers.noaa.mrms`.
- Latency is empty beyond the real-time claim already in the update cycle.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/mrms.md#catalog-reference).
