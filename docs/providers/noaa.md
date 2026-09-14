# NOAA datasets

NOAA datasets use several independent services. Choose a dataset below for its
query requirements, file format, and scientific limits. All currently supported
NOAA access is anonymous.

| Dataset | Read this guide | Download granularity |
|---|---|---|
| `ghcn-daily` | [Daily station observations](noaa-ghcn.md) | Station CSV for inclusive dates |
| `gsom` | [Monthly station summaries](noaa-gsom.md) | Complete UTC months |
| `gsoy` | [Annual station summaries](noaa-gsoy.md) (v0.10.0) | Complete UTC years |
| `climate-normals` | [30-year station normals](noaa-normals.md) (v0.11.0) | Whole-year or month-day windows per period |
| `lcd` | [Hourly airport observations](noaa-lcd.md) (v0.14.0) | Every report on whole days per station chunk |
| `nexrad-level2` | [Radar scans](noaa-nexrad.md) | Whole Level II scans |
| `nexrad-level3` | [Derived radar products](noaa-nexrad-level3.md) (v0.15) | Whole Level III product files, no reader |
| `mrms` | [MRMS gridded radar products](noaa-mrms.md) (v0.15.0) | Whole two-minute CONUS grids of one product, at most a day |
| `goes-abi` | [GOES imagery](noaa-goes.md) | Whole single-channel CONUS scenes |
| `goes-glm` | [GOES lightning detections](noaa-glm.md) (v0.15.0) | Whole 20-second detection files, at most a day |
| `storm-events` | [Storm Events](noaa-storm-events.md) | Whole annual details archives |
| `spc-tornado-reports` | [SPC tornado reports](noaa-spc-tornado.md) (v0.15.0) | Whole annual, half-decade, or decade files |
| `hurdat2` | [Tropical cyclone best tracks](noaa-hurdat2.md) (v0.12.0) | One whole basin file per revision |
| `coastwatch-sst` | [Sea-surface temperature](noaa-coastwatch.md) | Spatial and temporal CSV subsets |
| `coops-water-levels` | [Observed coastal water levels](noaa-coops.md) (v0.10.0) | One station and datum, at most 28 days |
| `coops-tide-predictions` | [Tide predictions](noaa-coops-predictions.md) (v0.14.0) | One station, datum, and interval, at most a year |

See the [generated catalog](../generated/catalog/noaa.md) for status,
capabilities, endpoints, and versions. Historical endpoint probes and candidate
sources are in [service research notes](noaa-services.md).

Geographic queries use bounding rectangles, which can include stations outside
a state's actual boundary. See [place lookup](../reference/places.md). Use
explicit station IDs when exact selection matters. NOAA data is generally a
U.S. Government work in the public domain; check each source's license.

## NEXRAD Level III products

See [NEXRAD Level III products](noaa-nexrad-level3.md).

## MRMS gridded radar products

See [MRMS gridded radar products](noaa-mrms.md).

## GOES ABI CONUS imagery

See [GOES ABI CONUS imagery](noaa-goes.md).

## GOES GLM lightning detections

See [GOES GLM lightning detections](noaa-glm.md).

## Storm Events annual details

See [Storm Events annual details](noaa-storm-events.md).

## SPC tornado reports

See [SPC tornado reports](noaa-spc-tornado.md).

## HURDAT2 best tracks

See [HURDAT2 best tracks](noaa-hurdat2.md).

## Global Summary of the Month

See [Global Summary of the Month](noaa-gsom.md).

## Global Summary of the Year

See [Global Summary of the Year](noaa-gsoy.md).

## U.S. Climate Normals

See [U.S. Climate Normals 1991-2020](noaa-normals.md).

## Local Climatological Data

See [Local Climatological Data](noaa-lcd.md).

## CoastWatch SST

See [CoastWatch SST](noaa-coastwatch.md).

## CO-OPS observed water levels

See [CO-OPS observed water levels](noaa-coops.md).

## CO-OPS tide predictions

See [CO-OPS tide predictions](noaa-coops-predictions.md).

## Access notes

See [service notes](noaa-services.md#access-notes).

## Query validation

Use the dataset guides above for supported query options.

## Data landscape

See the [research inventory](noaa-services.md#data-landscape).

## Datasets

See the [generated catalog](../generated/catalog/noaa.md).
