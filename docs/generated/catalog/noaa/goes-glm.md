# GOES lightning detections

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:goes-glm` · **Source only** · Install from [source](../../../project.md#source-installation) to use this dataset.

GOES Geostationary Lightning Mapper.

## At a glance

- Files: NetCDF4
- Selection: Whole 20-second detection files by inclusive UTC file-start time, at most one day
- Required inputs: Satellite and both timestamps
- Open locally: `usdata[netcdf]` · [Reader guide](../../../reference/readers.md)
- Examples: [glm flashes](https://usdata.dev/examples/glm-flashes/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `satellite` | Required GOES satellite number: 16, 17, 18, or 19. |

## Usage and limitations

[Usage guide](../../../providers/noaa-glm.md).

## Catalog reference

- Availability: Source only · intended for 0.15
- Domain: Weather satellites
- Catalog date range: 2018-02-13 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://registry.opendata.aws/noaa-goes/)
- License: US Government Work (public domain)
- Transport: `s3`
- Adapter: `usdata.providers.noaa.glm:GoesGlm`

[All NOAA datasets](../noaa.md).
