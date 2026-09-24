# GOES lightning detections

<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

`noaa:goes-glm` · **Released** · Included since usdata 0.15.

GOES Geostationary Lightning Mapper.

## At a glance

- Files: NetCDF4
- Selection: Whole 20-second detection files by inclusive UTC file-start time, at most one day
- Required inputs: Satellite and both timestamps
- Open locally: `usdata[netcdf]` · [Reader guide](../../../reference/readers.md)
- Examples: [Did lightning near the storm pick up before the Oklahoma City tornado report?](https://usdata.dev/examples/glm-flashes/); [Which severe reports came with rotation and lightning?](https://usdata.dev/examples/tornado-classification/); [For one Oklahoma tornado, do the two report archives agree on when and where it was, and what did radar, lightning, and the model analysis show at that place and time?](https://usdata.dev/examples/severe-weather-case-study/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `satellite` | Required GOES satellite number: 16, 17, 18, or 19. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `flash_lat` | degrees_north | Flash centroid latitude |
| `flash_lon` | degrees_east | Flash centroid longitude |
| `flash_area` | m2 | Flash footprint area |
| `flash_energy` | J | Flash radiant energy |
| `flash_time_offset_of_first_event` | CF datetime | Time of the flash's first event |
| `flash_time_offset_of_last_event` | CF datetime | Time of the flash's last event |
| `flash_quality_flag` | — | The source's own screening flag for the flash |
| `group_lat` | degrees_north | Group centroid latitude |
| `group_lon` | degrees_east | Group centroid longitude |
| `group_area` | m2 | Group footprint area |
| `group_energy` | J | Group radiant energy |
| `event_lat` | degrees_north | Event latitude |
| `event_lon` | degrees_east | Event longitude |
| `event_energy` | J | Event radiant energy |

## Usage and limitations

[Usage guide](../../../providers/noaa-glm.md).

## Catalog reference

- Availability: since 0.15
- Domain: Weather satellites
- Spatial resolution: 8 to 14 km across the instrument's field of view
- Temporal resolution: One detection file every 20 seconds
- Updates: New data is added as soon as it's available
- Longest query window: 1 day
- Terms of use: <https://www.noaa.gov/information-technology/open-data-dissemination>
- Citation: NOAA Geostationary Operational Environmental Satellites (GOES) 16, 17, 18 & 19 was accessed on [date] from https://registry.opendata.aws/noaa-goes
- Catalog date range: 2018-02-13 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://registry.opendata.aws/noaa-goes/)
- License: US Government Work (public domain)
- Transport: `s3`
- Adapter: `usdata.providers.noaa.glm:GoesGlm`

[All NOAA datasets](../noaa.md).
