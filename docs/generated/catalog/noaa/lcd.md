# Hourly airport observations

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:lcd` · **Released** · Included since usdata 0.14.

Local Climatological Data.

## At a glance

- Files: CSV
- Selection: Every report on whole calendar days per station; optional column filters
- Required inputs: Both dates; eleven-digit station IDs or a geographic query
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [hourly observations](https://usdata.dev/examples/hourly-observations/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `stations` | Station ids, comma-separated or a list; otherwise a location selects them. |
| `units` | metric (default) or standard. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `STATION` | — | Eleven-digit LCD station id |
| `DATE` | — | Report time in the station's local standard time, without an offset |
| `REPORT_TYPE` | — | FM-15 hourly, FM-16 special, FM-12 synoptic, SOD daily, SOM monthly |
| `HourlyDryBulbTemperature` | degrees Celsius | Hourly dry-bulb temperature (metric units) |
| `HourlyPrecipitation` | mm | Hourly precipitation; T marks a trace (metric units) |
| `DailyPrecipitation` | mm | Daily summary precipitation (metric units) |

## Usage and limitations

[Usage guide](../../../providers/noaa-lcd.md).

## Catalog reference

- Availability: since 0.14
- Domain: Surface weather
- Spatial resolution: Airport and first-order stations, addressed by eleven-digit station id
- Temporal resolution: Hourly, special, and synoptic reports, plus daily and monthly summaries
- Updates: Monthly
- Terms of use: <https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C00684/html>
- Citation: NOAA National Centers for Environmental Information, U.S. Local Climatological Data, accessed via usdata
- Coverage: not specified in the catalog
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.ncei.noaa.gov/products/land-based-station/local-climatological-data)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.lcd:LocalClimatologicalData`

[All NOAA datasets](../noaa.md).
