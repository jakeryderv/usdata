# MRMS gridded radar products

<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

`noaa:mrms` · **Released** · Included since usdata 0.15.

Multi-Radar Multi-Sensor (MRMS).

## At a glance

- Files: GRIB2 (gzipped)
- Selection: Whole two-minute CONUS grids of one product by inclusive UTC file stamp, at most one day
- Required inputs: Product name and both timestamps
- Open locally: `usdata[grib]` · [Reader guide](../../../reference/readers.md)
- Examples: [Where was the strongest mid-level rotation in each two-minute grid, and did it move toward the reported tornado?](https://usdata.dev/examples/mrms-rotation/); [Which severe reports came with rotation and lightning?](https://usdata.dev/examples/tornado-classification/); [For one Oklahoma tornado, do the two report archives agree on when and where it was, and what did radar, lightning, and the model analysis show at that place and time?](https://usdata.dev/examples/severe-weather-case-study/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `product` | Required product directory name, for example RotationTrackML30min_00.50; see the dataset guide for the supported list. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `RotationTrack30min_00.50` | 0.001 s-1 | 30-minute maximum low-level azimuthal shear |
| `RotationTrack60min_00.50` | 0.001 s-1 | 60-minute maximum low-level azimuthal shear |
| `RotationTrack120min_00.50` | 0.001 s-1 | 2-hour maximum low-level azimuthal shear, hourly files |
| `RotationTrackML30min_00.50` | 0.001 s-1 | 30-minute maximum mid-level azimuthal shear |
| `RotationTrackML60min_00.50` | 0.001 s-1 | 60-minute maximum mid-level azimuthal shear |
| `RotationTrackML120min_00.50` | 0.001 s-1 | 2-hour maximum mid-level azimuthal shear, hourly files |
| `MergedReflectivityQCComposite_00.50` | dBZ | Quality-controlled composite reflectivity |
| `MergedReflectivityComposite_00.50` | dBZ | Composite reflectivity without quality control |
| `ReflectivityAtLowestAltitude_00.50` | dBZ | Reflectivity at the lowest altitude with data |
| `MergedBaseReflectivityQC_00.50` | dBZ | Quality-controlled base reflectivity |
| `MESH_00.50` | mm | Maximum estimated size of hail |
| `MESH_Max_30min_00.50` | mm | 30-minute maximum estimated hail size |
| `MESH_Max_60min_00.50` | mm | 60-minute maximum estimated hail size |
| `VIL_00.50` | kg m-2 | Vertically integrated liquid |
| `VIL_Density_00.50` | g m-3 | Vertically integrated liquid density |
| `EchoTop_18_00.50` | km | 18 dBZ echo top height |
| `EchoTop_30_00.50` | km | 30 dBZ echo top height |
| `EchoTop_50_00.50` | km | 50 dBZ echo top height |
| `PrecipRate_00.00` | mm h-1 | Radar precipitation rate |
| `LightningProbabilityNext30minGrid_scale_1` | % | Probability of lightning in the next 30 minutes |

## Usage and limitations

[Usage guide](../../../providers/noaa-mrms.md).

## Catalog reference

- Availability: since 0.15
- Domain: Weather radar
- Spatial resolution: 0.01 degree CONUS grid (3,500 x 7,000 points); 0.005 degree for rotation tracks
- Temporal resolution: Two minutes; the two-hour rotation tracks are written hourly
- Updates: Data is delivered in real-time with a 2-minute update cycle
- Longest query window: 1 day
- Terms of use: <https://www.noaa.gov/information-technology/open-data-dissemination>
- Citation: NOAA Multi-Radar/Multi-Sensor System (MRMS) was accessed on [date] from https://registry.opendata.aws/noaa-mrms-pds
- Geographic bounds (WGS84): west -130°, south 20°, east -60°, north 55°
- Catalog date range: 2020-10-14 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://registry.opendata.aws/noaa-mrms-pds/)
- License: US Government Work (public domain)
- Transport: `s3`
- Adapter: `usdata.providers.noaa.mrms:Mrms`

[All NOAA datasets](../noaa.md).
