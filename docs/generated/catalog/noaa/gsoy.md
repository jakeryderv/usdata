# Global Summary of the Year

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

<!-- dataset-usage -->
[Usage guide](../../../providers/noaa-gsoy.md).

## Catalog reference

**Global Summary of the Year** · available · unreleased; planned 0.10

Annual station summaries derived from GHCN-Daily via the NCEI Access Data Service dataset global-summary-of-the-year. Selects complete UTC calendar years and explicit stations, or discovers stations through the search service.

- Domain: Surface weather
- Server-side subsetting: temporal, variable
- Homepage: https://www.ncei.noaa.gov/access/search/data-search/global-summary-of-the-year
- License: US Government Work (public domain)
- Extent: -180, -90, 180, 90
- Keywords: climate, annual, stations, temperature, precipitation, gsoy, ncei
- Adapter: `usdata.providers.noaa.gsoy:GlobalSummaryYearly`
