# Global Summary of the Month

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

<!-- dataset-usage -->
[Usage guide](../../../providers/noaa-gsom.md).

## Catalog reference

**Global Summary of the Month** · available · since 0.7

Monthly station summaries derived from GHCN-Daily (means, extremes, totals) via the NCEI Access Data Service dataset global-summary-of-the-month. Selects whole calendar months and explicit stations, or discovers stations through the companion search service.

- Domain: Surface weather
- Server-side subsetting: temporal, variable
- Homepage: https://www.ncei.noaa.gov/access/search/data-search/global-summary-of-the-month
- License: US Government Work (public domain)
- Extent: -180, -90, 180, 90
- Keywords: climate, monthly, stations, temperature, precipitation, gsom, ncei
- Adapter: `usdata.providers.noaa.gsom:GlobalSummaryMonthly`
