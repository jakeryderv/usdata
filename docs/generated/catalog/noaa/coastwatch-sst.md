# CoastWatch Blended Sea Surface Temperature

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

<!-- dataset-usage -->
[Usage guide](../../../providers/noaa-coastwatch.md).

## Catalog reference

**CoastWatch Blended Sea Surface Temperature** · available · since 0.5

NOAA geo-polar blended daily SST analysis (day and night) on a global 5 km grid, ERDDAP dataset noaacwBLENDEDsstDNDaily on the CoastWatch server, with server-side spatial, temporal, and variable subsetting. Raw CSV subsets retain grid coordinates and units without volatile NetCDF history.

- Domain: Satellite oceanography
- Server-side subsetting: spatial, temporal, variable
- Homepage: https://coastwatch.noaa.gov/erddap/griddap/noaacwBLENDEDsstDNDaily.html
- License: GHRSST free and open data
- Extent: -179.975, -89.975, 179.975, 89.975; 2019-07-22 to present
- Keywords: ocean, sst, sea surface temperature, satellite, erddap, coastwatch, gridded, blended
- Adapter: `usdata.providers.noaa.coastwatch:CoastwatchSst`
