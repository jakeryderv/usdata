# Streamflow and Water Daily Values

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

<!-- dataset-usage -->
[Usage guide](../../../providers/usgs-water-daily.md).

## Catalog reference

**Streamflow and Water Daily Values** · available · since 0.5

Daily statistics (streamflow, gage height, temperature) for USGS monitoring sites via the modern USGS Water Data OGC API. Anonymous, paginated CSV downloads filtered by site or bbox, dates, and parameter codes; daily mean by default, with units and quality metadata preserved.

- Domain: Water resources
- Server-side subsetting: spatial, temporal, variable
- Homepage: https://api.waterdata.usgs.gov/
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: water, streamflow, discharge, rivers, gages, hydrology, nwis
- Adapter: `usdata.providers.usgs.daily:WaterDaily`
