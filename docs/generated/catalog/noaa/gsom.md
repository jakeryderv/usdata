# Monthly station climate

<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

`noaa:gsom` · **Released** · Included since usdata 0.7.

Global Summary of the Month.

## At a glance

- Files: CSV
- Selection: Complete UTC calendar months touched by the query; station and element filters
- Required inputs: Both dates; station IDs or a geographic query
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [How did temperature and rainfall vary through the year?](https://usdata.dev/examples/monthly-climate/); [Was 2024 warmer or wetter than normal?](https://usdata.dev/examples/climate-anomalies/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `stations` | Station ids, comma-separated or a list; otherwise a location selects them. |
| `units` | metric (default) or standard. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `PRCP` | mm | Monthly precipitation total (metric units) |
| `TAVG` | degrees Celsius | Monthly mean temperature (metric units) |

## Usage and limitations

[Usage guide](../../../providers/noaa-gsom.md).

## Catalog reference

- Availability: since 0.7
- Domain: Surface weather
- Spatial resolution: Land surface stations, derived from GHCN-Daily
- Temporal resolution: Monthly
- Updates: Weekly
- Terms of use: <https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C00946/html>
- Citation: Lawrimore, Jay H.; Ray, Ron; Applequist, Scott; Korzeniewski, Bryant; Menne, Matthew J. (2016): Global Summary of the Month (GSOM), Version 1. NOAA National Centers for Environmental Information. https://doi.org/10.7289/V5QV3JJ5
- Geographic bounds (WGS84): west -180°, south -90°, east 180°, north 90°
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.ncei.noaa.gov/access/search/data-search/global-summary-of-the-month)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.gsom:GlobalSummaryMonthly`

[All NOAA datasets](../noaa.md).
