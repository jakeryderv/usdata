# RAP model output

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:rap` · **Released** · Included since usdata 0.20.

RAP Model Output.

## At a glance

- Files: GRIB2
- Selection: Files, whole or by named GRIB2 message, chosen by run initialization window, cycle hour, forecast hours, and file family
- Required inputs: Both timestamps, cycle, and forecast_hour
- Open locally: `usdata[grib]` · [Reader guide](../../../reference/readers.md)
- Examples: [rap environment](https://usdata.dev/examples/rap-environment/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `cycle` | Required UTC initialization hour of the run, 0 to 23. |
| `file` | File family: awp130 (default, 13 km CONUS pressure levels), awp130b (its secondary fields), prs (native-grid pressure levels), or nat (native levels). |
| `forecast_hour` | Required forecast hour(s): an integer, list, or comma-separated string; 0 to 21, or 0 to 51 for the 03, 09, 15, and 21 UTC runs. |
| `messages` | Optional GRIB2 messages to fetch instead of the whole file, spelled as the object's wgrib2 .idx sidecar spells them: 'SHORTNAME:level text', such as 'TMP:2 m above ground', with an optional ':step text'; one value, a list, or a comma-separated string. Short names are upper case and both fields match exactly. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `cape` | J/kg | Convective available potential energy, surface or a ground layer |
| `cin` | J/kg | Convective inhibition, surface or a ground layer |
| `hlcy` | m2/s2 | Storm-relative helicity over the 0-1 km and 0-3 km layers |
| `refc` | dBZ | Composite reflectivity |
| `2t` | K | 2 m temperature |
| `2d` | K | 2 m dewpoint temperature |

## Usage and limitations

[Usage guide](../../../providers/noaa-rap.md).

## Catalog reference

- Availability: since 0.20
- Domain: Weather models
- Spatial resolution: 13 km Lambert conformal CONUS grid, 451 x 337 points, for the awp130 family
- Temporal resolution: Hourly runs; forecast hours to 21, or to 51 from the 03, 09, 15, and 21 UTC runs
- Updates: Hourly
- Longest query window: 1 day
- Terms of use: <https://www.noaa.gov/information-technology/open-data-dissemination>
- Citation: NOAA Rapid Refresh (RAP) was accessed on [date] from https://registry.opendata.aws/noaa-rap
- Catalog date range: 2021-02-22 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://registry.opendata.aws/noaa-rap/)
- License: US Government Work (public domain)
- Transport: `s3`
- Adapter: `usdata.providers.noaa.rap:Rap`

[All NOAA datasets](../noaa.md).
