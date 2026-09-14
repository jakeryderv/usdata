# MRMS gridded radar products

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:mrms` · **Source only** · Install from [source](../../../project.md#source-installation) to use this dataset.

Multi-Radar Multi-Sensor (MRMS).

## At a glance

- Files: GRIB2 (gzipped)
- Selection: Whole two-minute CONUS grids of one product by inclusive UTC file stamp, at most one day
- Required inputs: Product name and both timestamps
- Open locally: Local files; no bundled reader for this format
- Examples: [mrms rotation](https://usdata.dev/examples/mrms-rotation/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `product` | Required product directory name, for example RotationTrackML30min_00.50; see the dataset guide for the supported list. |

## Usage and limitations

[Usage guide](../../../providers/noaa-mrms.md).

## Catalog reference

- Availability: Source only · intended for 0.15
- Domain: Weather radar
- Geographic bounds (WGS84): west -130°, south 20°, east -60°, north 55°
- Catalog date range: 2020-10-14 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://registry.opendata.aws/noaa-mrms-pds/)
- License: US Government Work (public domain)
- Transport: `s3`
- Adapter: `usdata.providers.noaa.mrms:Mrms`

[All NOAA datasets](../noaa.md).
