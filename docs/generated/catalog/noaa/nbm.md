# NBM forecast guidance

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:nbm` · **Source only** · Install from [source](../../../install.md#source-installation) to use this dataset.

National Blend of Models.

## At a glance

- Files: GRIB2
- Selection: Regional core files, whole or by named GRIB2 message, chosen by run initialization window, cycle hour, forecast hours, and region
- Required inputs: Both timestamps, cycle, and forecast_hour
- Open locally: `usdata[grib]` · [Reader guide](../../../reference/readers.md)
- Examples: [nbm forecast](https://usdata.dev/examples/nbm-forecast/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `cycle` | Required UTC initialization hour of the run, 0 to 23. |
| `forecast_hour` | Required forecast hour(s): an integer, list, or comma-separated string, 1 to 264; hourly to 36, then every 3 hours, then every 6, on a schedule that varies by cycle. |
| `messages` | Optional GRIB2 messages to fetch instead of the whole file, spelled as the object's wgrib2 .idx sidecar spells them: 'SHORTNAME:level text', such as 'TMP:2 m above ground', with an optional ':step text'; one value, a list, or a comma-separated string. Short names are upper case and both fields match exactly. |
| `region` | Grid: co (default, 2.5 km CONUS), ak (Alaska), hi (Hawaii), pr (Puerto Rico), or gu (Guam). |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `2t` | K | 2 m temperature |
| `2d` | K | 2 m dewpoint temperature |
| `tp` | kg/m2 | Total precipitation accumulated over the step |

## Usage and limitations

[Usage guide](../../../providers/noaa-nbm.md).

## Catalog reference

- Availability: Source only · intended for 0.20
- Domain: Weather models
- Spatial resolution: 2.5 km Lambert conformal CONUS grid, 2345 x 1597 points; separate Alaska, Hawaii, Puerto Rico, and Guam grids
- Temporal resolution: Hourly runs; forecast hours hourly to 36, then every 3 hours to about 190, then every 6 hours to 264, on a schedule that varies by cycle
- Updates: Hourly
- Longest query window: 1 day
- Terms of use: <https://www.noaa.gov/information-technology/open-data-dissemination>
- Citation: NOAA National Blend of Models (NBM) was accessed on [date] from https://registry.opendata.aws/noaa-nbm
- Catalog date range: 2020-09-29 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://registry.opendata.aws/noaa-nbm/)
- License: US Government Work (public domain)
- Transport: `s3`
- Adapter: `usdata.providers.noaa.nbm:Nbm`

[All NOAA datasets](../noaa.md).
