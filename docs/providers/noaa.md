# NOAA datasets

NOAA datasets use several independent services. Choose a dataset below for its
query requirements, file format, and scientific limits. All currently supported
NOAA access is anonymous.

| Dataset | Read this guide | Download granularity |
|---|---|---|
| `ghcn-daily` | [Daily station observations](noaa-ghcn.md) | Station CSV for inclusive dates |
| `gsom` | [Monthly station summaries](noaa-gsom.md) | Complete UTC months |
| `gsoy` | [Annual station summaries](noaa-gsoy.md) (v0.10 / source) | Complete UTC years |
| `nexrad-level2` | [Radar scans](noaa-nexrad.md) | Whole Level II scans |
| `goes-abi` | [GOES imagery](noaa-goes.md) | Whole single-channel CONUS scenes |
| `storm-events` | [Storm Events](noaa-storm-events.md) | Whole annual details archives |
| `coastwatch-sst` | [Sea-surface temperature](noaa-coastwatch.md) | Spatial and temporal CSV subsets |
| `coops-water-levels` | [Observed coastal water levels](noaa-coops.md) (v0.10 / source) | One station and datum, at most 28 days |

See the [generated catalog](../generated/catalog/noaa.md) for status,
capabilities, endpoints, and versions. Historical endpoint probes and candidate
sources are in [service research notes](noaa-services.md).

Geographic queries use bounding rectangles, which can include stations outside
a state's actual boundary. See [place lookup](../reference/places.md). Use
explicit station IDs when exact selection matters. NOAA data is generally a
U.S. Government work in the public domain; check each source's license.

## GOES ABI CONUS imagery

See [GOES ABI CONUS imagery](noaa-goes.md).

## Storm Events annual details

See [Storm Events annual details](noaa-storm-events.md).

## Global Summary of the Month

See [Global Summary of the Month](noaa-gsom.md).

## Global Summary of the Year

See [Global Summary of the Year](noaa-gsoy.md).

## CoastWatch SST

See [CoastWatch SST](noaa-coastwatch.md).

## CO-OPS observed water levels

See [CO-OPS observed water levels](noaa-coops.md).

## Access notes

See [service notes](noaa-services.md#access-notes).

## Query validation

Use the dataset guides above for supported query options.

## Data landscape

See the [research inventory](noaa-services.md#data-landscape).

## Datasets

See the [generated catalog](../generated/catalog/noaa.md).
