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

## Usage and limitations

[Usage guide](../../../providers/noaa-lcd.md).

## Catalog reference

- Availability: since 0.14
- Domain: Surface weather
- Coverage: not specified in the catalog
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.ncei.noaa.gov/products/land-based-station/local-climatological-data)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.lcd:LocalClimatologicalData`

[All NOAA datasets](../noaa.md).
