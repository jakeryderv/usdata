# Daily water observations

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`usgs:water-daily` · **Released** · Included since usdata 0.5.

Streamflow and Water Daily Values.

## At a glance

- Files: CSV
- Selection: Site observations for inclusive local calendar dates; parameter and statistic filters
- Required inputs: Both dates; site IDs or a geographic query
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [weather and streamflow](../../../examples/weather-and-streamflow/example.md)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `site` | One quoted USGS monitoring ID, with or without the USGS- prefix. |
| `sites` | Several quoted monitoring IDs, comma-separated or a list. |
| `statistic_id` | Quoted five-digit statistic code; default 00003 (daily mean). |

## Usage and limitations

[Usage guide](../../../providers/usgs-water-daily.md).

## Catalog reference

- Availability: since 0.5
- Domain: Water resources
- Coverage: not specified in the catalog
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://api.waterdata.usgs.gov/)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.usgs.daily:WaterDaily`

[All USGS datasets](../usgs.md).
