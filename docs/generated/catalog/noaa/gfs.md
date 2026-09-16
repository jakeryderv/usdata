# GFS model output

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:gfs` · **Released** · Included since usdata 0.15.

GFS Forecast Model Output.

## At a glance

- Files: GRIB2
- Selection: Global files, whole or by named GRIB2 message, chosen by run initialization window, cycle hour, forecast hours, and grid resolution
- Required inputs: Both timestamps, cycle, and forecast_hour
- Open locally: `usdata[grib]` · [Reader guide](../../../reference/readers.md)
- Examples: [gfs environment](https://usdata.dev/examples/gfs-environment/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `cycle` | Required UTC initialization hour of the run: 0, 6, 12, or 18. |
| `forecast_hour` | Required forecast hour(s): an integer, list, or comma-separated string, 0 to 384; hourly to 120 then every 3 hours at 0p25, every 3 hours at 0p50 and 1p00. |
| `messages` | Optional GRIB2 messages to fetch instead of the whole file, spelled as the object's wgrib2 .idx sidecar spells them: 'SHORTNAME:level text', such as 'TMP:2 m above ground', with an optional ':step text'; one value, a list, or a comma-separated string. Short names are upper case and both fields match exactly. |
| `resolution` | Grid spacing: 0p25 (default, 0.25 degree), 0p50, or 1p00. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `cape` | J/kg | Convective available potential energy, surface or a ground layer |
| `cin` | J/kg | Convective inhibition, surface or a ground layer |
| `hlcy` | m2/s2 | Storm-relative helicity over the 0-3 km layer |
| `refc` | dB | Composite reflectivity |
| `10u` | m/s | 10 m eastward wind component |
| `10v` | m/s | 10 m northward wind component |
| `2t` | K | 2 m temperature |
| `2d` | K | 2 m dewpoint temperature |
| `prmsl` | Pa | Mean sea-level pressure |
| `pwat` | kg/m2 | Precipitable water |

## Usage and limitations

[Usage guide](../../../providers/noaa-gfs.md).

## Catalog reference

- Availability: since 0.15
- Domain: Weather models
- Spatial resolution: 0.25, 0.5, or 1 degree global latitude-longitude grid, chosen with resolution
- Temporal resolution: Hourly to 120 then three-hourly to 384 at 0p25; three-hourly at 0p50 and 1p00
- Updates: 4 times a day, every 6 hours starting at midnight UTC
- Longest query window: 1 day
- Terms of use: <https://www.noaa.gov/information-technology/open-data-dissemination>
- Citation: NOAA Global Forecast System (GFS) was accessed on [date] from https://registry.opendata.aws/noaa-gfs-bdp-pds
- Catalog date range: 2021-03-22 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://registry.opendata.aws/noaa-gfs-bdp-pds/)
- License: US Government Work (public domain)
- Transport: `s3`
- Adapter: `usdata.providers.noaa.gfs:Gfs`

[All NOAA datasets](../noaa.md).
