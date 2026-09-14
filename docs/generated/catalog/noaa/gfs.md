# GFS model output

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:gfs` · **Released** · Included since usdata 0.15.

GFS Forecast Model Output.

## At a glance

- Files: GRIB2
- Selection: Whole global files by run initialization window, cycle hour, forecast hours, and grid resolution, at most one day
- Required inputs: Both timestamps, cycle, and forecast_hour
- Open locally: `usdata[grib]` · [Reader guide](../../../reference/readers.md)
- Examples: [gfs environment](https://usdata.dev/examples/gfs-environment/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `cycle` | Required UTC initialization hour of the run: 0, 6, 12, or 18. |
| `forecast_hour` | Required forecast hour(s): an integer, list, or comma-separated string, 0 to 384; hourly to 120 then every 3 hours at 0p25, every 3 hours at 0p50 and 1p00. |
| `resolution` | Grid spacing: 0p25 (default, 0.25 degree), 0p50, or 1p00. |

## Usage and limitations

[Usage guide](../../../providers/noaa-gfs.md).

## Catalog reference

- Availability: since 0.15
- Domain: Weather models
- Catalog date range: 2021-03-22 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://registry.opendata.aws/noaa-gfs-bdp-pds/)
- License: US Government Work (public domain)
- Transport: `s3`
- Adapter: `usdata.providers.noaa.gfs:Gfs`

[All NOAA datasets](../noaa.md).
