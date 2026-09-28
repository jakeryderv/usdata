<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

## Reference

`noaa:ersst` · **Source only** · Install from [source](../install.md#source-installation) to use this dataset. ERSST v6 Monthly Sea Surface Temperature.

### At a glance

- Files: NetCDF4
- Selection: Whole global monthly files, one for every month the window touches
- Required inputs: Both dates (selects the months they span)
- Open locally: `usdata[netcdf]` · [Reader guide](../reference/readers.md)
- On usdata.dev: [Monthly global 2 degree sea surface temperature since 1850](https://usdata.dev/datasets/noaa/ersst/), with a walkthrough

### Parameters

This dataset accepts no provider-specific parameters.

### Variables

| Variable | Units | Meaning |
|---|---|---|
| `sst` | degree_C | Extended reconstructed sea surface temperature |
| `ssta` | degree_C | Anomaly from the 1991-2020 ERSSTv6 climatology |

### Catalog facts

- Availability: Source only · intended for 0.33
- Domain: Ocean physics
- Spatial resolution: 2.0 degree grid
- Temporal resolution: Monthly means
- Updates: Monthly, around the third: each update writes the month just ended and rewrites the month before it
- Terms of use: <https://www.ncei.noaa.gov/products/extended-reconstructed-sst>
- Citation: Huang, B., X. Yin, T. Boyer, C. Liu, M. Menne, Y. D. Rao, T. Smith, R. Vose, and H.-M. Zhang, 2025: Extended Reconstructed Sea Surface Temperature Version 6 (ERSSTv6): Part I. An Artificial Neural Network Approach. Journal of Climate, 38, 1105-1121, doi:10.1175/JCLI-D-23-0707.1
- Geographic bounds (WGS84): west -180°, south -89°, east 180°, north 89°
- Catalog date range: 1850-01-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.ncei.noaa.gov/products/extended-reconstructed-sst)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.ersst:Ersst`
