# GOES-R ABI CONUS Cloud and Moisture Imagery

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

<!-- dataset-usage -->
[Usage guide](../../../providers/noaa-goes.md).

## Catalog reference

**GOES-R ABI CONUS Cloud and Moisture Imagery** · available · since 0.8

Single-channel CONUS Cloud and Moisture Imagery (ABI-L2-CMIPC) from GOES-16, 17, 18, and 19 in anonymous NOAA S3 buckets. Select an explicit satellite, channel, and scan-start interval; each asset is a complete NetCDF scene with no geographic or variable subsetting.

- Domain: Weather satellites
- Server-side subsetting: temporal
- Homepage: https://registry.opendata.aws/noaa-goes/
- License: US Government Work (public domain)
- Extent: 2017-02-28 to present
- Keywords: satellite, imagery, goes, abi, clouds, infrared, reflectance, netcdf, conus
- Adapter: `usdata.providers.noaa.goes:GoesAbi`
