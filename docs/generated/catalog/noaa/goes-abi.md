# GOES CONUS imagery

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:goes-abi` · **Released** · Included since usdata 0.8.

GOES-R ABI CONUS Cloud and Moisture Imagery.

## At a glance

- Files: NetCDF4
- Selection: Whole single-channel CONUS scenes by inclusive UTC scan-start time
- Required inputs: Satellite, channel, and both timestamps
- Open locally: `usdata[netcdf]` · [Reader guide](../../../reference/readers.md)
- Examples: [goes imagery](https://usdata.dev/examples/goes-imagery/), [event context](https://usdata.dev/examples/event-context/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `channel` | Required ABI channel, 1 to 16 or C01 to C16. |
| `product` | ABI product; only ABI-L2-CMIPC is supported. |
| `satellite` | Required GOES satellite number: 16, 17, 18, or 19. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `CMI` | — | Cloud and moisture imagery; reflectance factor or brightness temperature by band |
| `DQF` | — | Per-pixel data quality flags for CMI |

## Usage and limitations

[Usage guide](../../../providers/noaa-goes.md).

## Catalog reference

- Availability: since 0.8
- Domain: Weather satellites
- Spatial resolution: 0.5 km to 2 km at nadir, by ABI band
- Temporal resolution: One CONUS scan every 5 minutes on average
- Updates: New data is added as soon as it's available
- Longest query window: 7 days
- Terms of use: <https://www.noaa.gov/information-technology/open-data-dissemination>
- Citation: NOAA Geostationary Operational Environmental Satellites (GOES) 16, 17, 18 & 19 was accessed on [date] from https://registry.opendata.aws/noaa-goes
- Catalog date range: 2017-02-28 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://registry.opendata.aws/noaa-goes/)
- License: US Government Work (public domain)
- Transport: `s3`
- Adapter: `usdata.providers.noaa.goes:GoesAbi`

[All NOAA datasets](../noaa.md).
