# Daily water observations

<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

`usgs:water-daily` · **Released** · Included since usdata 0.5.

Streamflow and Water Daily Values.

## At a glance

- Files: CSV
- Selection: Site observations for inclusive local calendar dates; parameter and statistic filters
- Required inputs: Both dates; site IDs or a geographic query
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- On usdata.dev: [Daily water observations](https://usdata.dev/datasets/usgs/water-daily/), with a walkthrough
- Studies: [How can I preserve weather and streamflow inputs together?](https://usdata.dev/studies/weather-and-streamflow/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `site` | One USGS monitoring ID, with or without the USGS- prefix. |
| `sites` | Several monitoring IDs, comma-separated or a list. |
| `statistic_id` | Five-digit statistic code; default 00003 (daily mean). |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `00060` | cubic feet per second | Discharge (streamflow) |
| `00065` | feet | Gage height |
| `00010` | degrees Celsius | Water temperature |

## Usage and limitations

[Usage guide](../../../providers/usgs-water-daily.md).

## Catalog reference

- Availability: since 0.5
- Domain: Water resources
- Spatial resolution: USGS monitoring locations, one site per record
- Temporal resolution: Daily
- Updates: Daily values are automatically calculated from the continuous data of the same parameter code
- Terms of use: <https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits>
- Citation: U.S. Geological Survey, Water Data for the Nation daily values, accessed via usdata
- Coverage: not specified in the catalog
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://api.waterdata.usgs.gov/)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.usgs.daily:WaterDaily`

[All USGS datasets](../usgs.md).
