<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

## Reference

`noaa:enso-indices` · **Released** · Included since usdata 0.33. CPC ENSO Indices (RONI and ONI).

### At a glance

- Files: whitespace-delimited text (no reader)
- Selection: One whole index table, every season from DJF 1950; select seasons locally
- Required inputs: Optional index (roni or oni); no dates or geographic filters
- Open locally: Local files; no bundled reader for this format
- On usdata.dev: [Seasonal El Niño indices, the official RONI and the traditional ONI](https://usdata.dev/datasets/noaa/enso-indices/), with a walkthrough
- Studies: [How have strong El Niño winters changed U.S. snowfall, and what does that suggest for 2026–27?](https://usdata.dev/studies/el-nino-snowfall/)

### Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `index` | Index table: roni (default, the Relative Oceanic Niño Index NOAA uses officially) or oni (the traditional Oceanic Niño Index). |

### Variables

| Variable | Units | Meaning |
|---|---|---|
| `SEAS` | — | Three-month season, such as DJF |
| `YR` | — | Year of the season's middle month |
| `ANOM` | degree_C | Index value: the season's anomaly |
| `TOTAL` | degree_C | Niño 3.4 mean temperature; ONI table only |

### Catalog facts

- Availability: since 0.33
- Domain: Climate
- Spatial resolution: One value for the Niño 3.4 region, 5N-5S and 170W-120W
- Temporal resolution: Overlapping three-month seasons, one per month
- Updates: Monthly, by the 5th
- Terms of use: <https://www.weather.gov/disclaimer>
- Citation: NOAA Climate Prediction Center, Relative Oceanic Niño Index and Oceanic Niño Index, accessed via usdata
- Geographic bounds (WGS84): west -170°, south -5°, east -120°, north 5°
- Catalog date range: 1949-12-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.enso:EnsoIndices`
