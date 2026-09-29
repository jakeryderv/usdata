<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

## Reference

`noaa:goes-abi` · **Released** · Included since usdata 0.8. GOES-R ABI Imagery and Cloud-Top Products.

### At a glance

- Files: NetCDF4
- Selection: Whole scenes of one ABI product by inclusive UTC scan-start time, with one channel or mesoscale sector where the product has them
- Required inputs: Satellite and both timestamps; product (default ABI-L2-CMIPC); channel for CMIP products; sector for mesoscale products
- Open locally: `usdata[netcdf]` · [Reader guide](../reference/readers.md)
- On usdata.dev: [GOES ABI imagery, multiband scenes, and cloud-top products](https://usdata.dev/datasets/noaa/goes-abi/), with a walkthrough
- Studies: [How did central Plains infrared cloud patterns change over fifteen minutes?](https://usdata.dev/studies/goes-mesoscale/); [What did radar and satellites show around a reported tornado?](https://usdata.dev/studies/event-context/)

### Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `channel` | ABI channel, 1 to 16 or C01 to C16. Required for ABI-L2-CMIP products only. |
| `product` | ABI product directory, such as ABI-L2-MCMIPC: CMIP (one channel) or MCMIP (16 channels) imagery, or cloud-top ACHA height, ACHT temperature (F and M only), CTP pressure (C and F only), or ACTP phase, ending in C (CONUS), F (full disk), or M (mesoscale). Default ABI-L2-CMIPC. |
| `satellite` | Required GOES satellite number: 16, 17, 18, or 19. |
| `sector` | Mesoscale sector M1 or M2. Required for products ending in M only. |

### Variables

| Variable | Units | Meaning |
|---|---|---|
| `CMI` | — | CMIP cloud and moisture imagery; reflectance factor or brightness temperature by band |
| `DQF` | 1 | Per-pixel data quality flags in CMIP and every cloud-top product |
| `CMI_C01` | 1 | MCMIP band 1 (0.47 µm, blue visible) reflectance factor on the 2 km grid |
| `CMI_C02` | 1 | MCMIP band 2 (0.64 µm, red visible) reflectance factor on the 2 km grid |
| `CMI_C03` | 1 | MCMIP band 3 (0.86 µm, veggie near-infrared) reflectance factor on the 2 km grid |
| `CMI_C04` | 1 | MCMIP band 4 (1.37 µm, cirrus near-infrared) reflectance factor on the 2 km grid |
| `CMI_C05` | 1 | MCMIP band 5 (1.6 µm, snow/ice near-infrared) reflectance factor on the 2 km grid |
| `CMI_C06` | 1 | MCMIP band 6 (2.2 µm, cloud particle size near-infrared) reflectance factor on the 2 km grid |
| `CMI_C07` | K | MCMIP band 7 (3.9 µm, shortwave window infrared) brightness temperature on the 2 km grid |
| `CMI_C08` | K | MCMIP band 8 (6.2 µm, upper-level water vapor) brightness temperature on the 2 km grid |
| `CMI_C09` | K | MCMIP band 9 (6.9 µm, mid-level water vapor) brightness temperature on the 2 km grid |
| `CMI_C10` | K | MCMIP band 10 (7.3 µm, lower-level water vapor) brightness temperature on the 2 km grid |
| `CMI_C11` | K | MCMIP band 11 (8.4 µm, cloud-top phase infrared) brightness temperature on the 2 km grid |
| `CMI_C12` | K | MCMIP band 12 (9.6 µm, ozone infrared) brightness temperature on the 2 km grid |
| `CMI_C13` | K | MCMIP band 13 (10.3 µm, clean longwave window) brightness temperature on the 2 km grid |
| `CMI_C14` | K | MCMIP band 14 (11.2 µm, longwave window) brightness temperature on the 2 km grid |
| `CMI_C15` | K | MCMIP band 15 (12.3 µm, dirty longwave window) brightness temperature on the 2 km grid |
| `CMI_C16` | K | MCMIP band 16 (13.3 µm, CO2 longwave infrared) brightness temperature on the 2 km grid |
| `DQF_C01` | 1 | MCMIP per-pixel data quality flags for CMI_C01 |
| `DQF_C02` | 1 | MCMIP per-pixel data quality flags for CMI_C02 |
| `DQF_C03` | 1 | MCMIP per-pixel data quality flags for CMI_C03 |
| `DQF_C04` | 1 | MCMIP per-pixel data quality flags for CMI_C04 |
| `DQF_C05` | 1 | MCMIP per-pixel data quality flags for CMI_C05 |
| `DQF_C06` | 1 | MCMIP per-pixel data quality flags for CMI_C06 |
| `DQF_C07` | 1 | MCMIP per-pixel data quality flags for CMI_C07 |
| `DQF_C08` | 1 | MCMIP per-pixel data quality flags for CMI_C08 |
| `DQF_C09` | 1 | MCMIP per-pixel data quality flags for CMI_C09 |
| `DQF_C10` | 1 | MCMIP per-pixel data quality flags for CMI_C10 |
| `DQF_C11` | 1 | MCMIP per-pixel data quality flags for CMI_C11 |
| `DQF_C12` | 1 | MCMIP per-pixel data quality flags for CMI_C12 |
| `DQF_C13` | 1 | MCMIP per-pixel data quality flags for CMI_C13 |
| `DQF_C14` | 1 | MCMIP per-pixel data quality flags for CMI_C14 |
| `DQF_C15` | 1 | MCMIP per-pixel data quality flags for CMI_C15 |
| `DQF_C16` | 1 | MCMIP per-pixel data quality flags for CMI_C16 |
| `HT` | m | ACHA cloud-top height |
| `TEMP` | K | ACHT cloud-top temperature |
| `PRES` | hPa | CTP cloud-top pressure |
| `Phase` | 1 | ACTP cloud-top phase: clear sky, liquid water, supercooled liquid water, mixed phase, ice, or unknown |

### Catalog facts

- Availability: since 0.8
- Domain: Weather satellites
- Spatial resolution: Imagery 0.5 km to 2 km at nadir by band, MCMIP bands on the 2 km grid; cloud-top products 2 km to 10 km at nadir
- Temporal resolution: CONUS every 5 minutes; full disk every 10 minutes in Mode 6 (15 in Mode 3, 5 in Mode 4); two mesoscale sectors every 60 seconds or one every 30 seconds
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
