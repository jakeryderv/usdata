<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

## Reference

`noaa:goes-abi` · **Released** · Included since usdata 0.8. GOES-R ABI Cloud and Moisture Imagery.

### At a glance

- Files: NetCDF4
- Selection: Whole single-channel scenes by inclusive UTC scan-start time and explicit mesoscale sector
- Required inputs: Satellite, channel, both timestamps; product and sector for mesoscale
- Open locally: `usdata[netcdf]` · [Reader guide](../reference/readers.md)
- On usdata.dev: [GOES CONUS and mesoscale imagery](https://usdata.dev/datasets/noaa/goes-abi/), with a walkthrough
- Studies: [How did central Plains infrared cloud patterns change over fifteen minutes?](https://usdata.dev/studies/goes-mesoscale/); [What did radar and satellites show around a reported tornado?](https://usdata.dev/studies/event-context/)

### Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `channel` | Required ABI channel, 1 to 16 or C01 to C16. |
| `product` | ABI-L2-CMIPC (CONUS, default) or ABI-L2-CMIPM (mesoscale). |
| `satellite` | Required GOES satellite number: 16, 17, 18, or 19. |
| `sector` | Required for ABI-L2-CMIPM: M1 or M2. Omit for CONUS. |

### Variables

| Variable | Units | Meaning |
|---|---|---|
| `CMI` | — | Cloud and moisture imagery; reflectance factor or brightness temperature by band |
| `DQF` | — | Per-pixel data quality flags for CMI |

### Catalog facts

- Availability: since 0.8
- Domain: Weather satellites
- Spatial resolution: 0.5 km to 2 km at nadir, by ABI band
- Temporal resolution: CONUS every 5 minutes; two mesoscale sectors every 60 seconds or one every 30 seconds
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
