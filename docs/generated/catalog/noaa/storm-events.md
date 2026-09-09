# Storm Events Database

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

<!-- dataset-usage -->
[Usage guide](../../../providers/noaa-storm-events.md).

## Catalog reference

**Storm Events Database** · available · since 0.8

NCEI's significant-weather event details since 1950, with locations, impacts, and narratives. Anonymous whole-year gzipped CSV archives; select the latest creation-date revision for each requested year. No server-side row, location, or variable subsetting. Historical event coverage and reporting practices vary; fatalities and locations tables are separate products not included by this adapter.

- Domain: Severe weather
- Server-side subsetting: none
- Homepage: https://www.ncei.noaa.gov/access/storm-events-database/
- License: US Government Work (public domain)
- Extent: 1950-01-01 to present
- Keywords: storms, tornado, hail, wind, flood, damage, severe weather, events
- Adapter: `usdata.providers.noaa.storm_events:StormEvents`
