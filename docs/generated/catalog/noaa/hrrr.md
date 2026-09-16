# HRRR model output

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:hrrr` · **Released** · Included since usdata 0.15.

HRRR Forecast Model Output.

## At a glance

- Files: GRIB2
- Selection: Whole CONUS files by run initialization window, cycle hour, forecast hours, and file variant, at most one day
- Required inputs: Both timestamps, cycle, and forecast_hour
- Open locally: `usdata[grib]` · [Reader guide](../../../reference/readers.md)
- Examples: [hrrr environment](https://usdata.dev/examples/hrrr-environment/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `cycle` | Required UTC initialization hour of the run, 0 to 23. |
| `file` | File variant: sfc (default, 2-D fields), prs (pressure levels), or nat (native levels). |
| `forecast_hour` | Required forecast hour(s): an integer, list, or comma-separated string; 0 to 18, or 0 to 48 for the 00, 06, 12, and 18 UTC runs. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `cape` | J/kg | Convective available potential energy, surface or a ground layer |
| `cin` | J/kg | Convective inhibition, surface or a ground layer |
| `hlcy` | m2/s2 | Storm-relative helicity over the 0-1 km and 0-3 km layers |
| `refc` | dBZ | Composite reflectivity |
| `10u` | m/s | 10 m eastward wind component |
| `10v` | m/s | 10 m northward wind component |
| `2t` | K | 2 m temperature |
| `2d` | K | 2 m dewpoint temperature |

## Usage and limitations

[Usage guide](../../../providers/noaa-hrrr.md).

## Catalog reference

- Availability: since 0.15
- Domain: Weather models
- Spatial resolution: 3 km Lambert conformal CONUS grid, 1799 x 1059 points
- Temporal resolution: Hourly runs; forecast hours to 18, or to 48 from the 00, 06, 12, and 18 UTC runs
- Updates: Hourly
- Longest query window: 1 day
- Terms of use: <https://www.noaa.gov/information-technology/open-data-dissemination>
- Citation: NOAA High-Resolution Rapid Refresh (HRRR) Model was accessed on [date] from https://registry.opendata.aws/noaa-hrrr-pds
- Catalog date range: 2014-07-30 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://registry.opendata.aws/noaa-hrrr-pds/)
- License: US Government Work (public domain)
- Transport: `s3`
- Adapter: `usdata.providers.noaa.hrrr:Hrrr`

[All NOAA datasets](../noaa.md).
