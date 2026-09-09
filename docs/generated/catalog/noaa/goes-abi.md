# GOES CONUS imagery

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:goes-abi` · **Released** · Included since usdata 0.8.

GOES-R ABI CONUS Cloud and Moisture Imagery.

## At a glance

- Files: NetCDF4
- Selection: Whole single-channel CONUS scenes by inclusive UTC scan-start time
- Required inputs: Satellite, channel, and both timestamps
- Open locally: `usdata[netcdf]` · [Reader guide](../../../reference/readers.md)
- Examples: [goes imagery](../../../../examples/goes-imagery/example.ipynb)

## Usage and limitations

<!-- dataset-usage -->
[Usage guide](../../../providers/noaa-goes.md).

## Catalog reference

- Availability: since 0.8
- Domain: Weather satellites
- Catalog date range: 2017-02-28 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://registry.opendata.aws/noaa-goes/)
- License: US Government Work (public domain)
- Transport: `s3`
- Adapter: `usdata.providers.noaa.goes:GoesAbi`

[All NOAA datasets](../noaa.md).
