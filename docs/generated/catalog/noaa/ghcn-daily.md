# GHCN-Daily Station Observations

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

<!-- dataset-usage -->
[Usage guide](../../../providers/noaa-ghcn.md).

## Catalog reference

**GHCN-Daily Station Observations** · available · since 0.2

Global Historical Climatology Network daily summaries: temperature, precipitation, snow, and other elements from land surface stations, served by the NCEI Access Data Service with station and date filtering.

- Domain: Surface weather
- Server-side subsetting: temporal, variable
- Homepage: https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily
- License: US Government Work (public domain)
- Extent: -180, -90, 180, 90; 1763-01-01 to present
- Keywords: climate, weather, temperature, precipitation, snow, stations, daily, ghcn, ncei
- Adapter: `usdata.providers.noaa.ghcnd:GhcnDaily`
