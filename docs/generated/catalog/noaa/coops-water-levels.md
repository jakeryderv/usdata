# CO-OPS Observed Water Levels

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

<!-- dataset-usage -->
[Usage guide](../../../providers/noaa-coops.md).

## Catalog reference

**CO-OPS Observed Water Levels** · available · unreleased; planned 0.10

Preliminary or verified six-minute observed water levels from the anonymous CO-OPS Data API. Select one station, an explicit vertical datum, units, and a UTC interval of at most 28 days. Raw CSV retains quality flags; predictions and station discovery are not included.

- Domain: Sea level and tides
- Server-side subsetting: temporal
- Homepage: https://api.tidesandcurrents.noaa.gov/api/prod/
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: tides, water level, sea level, coastal, coops, nwlon, stations
- Adapter: `usdata.providers.noaa.coops:CoopsWaterLevels`
