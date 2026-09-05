# Datasets

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

| Id | Title | Provider | Protocol | Server-side subsetting |
|---|---|---|---|---|
| [`noaa:coastwatch-sst`](#noaacoastwatch-sst) | CoastWatch Sea Surface Temperature | noaa | erddap | spatial, temporal, variable |
| [`noaa:ghcn-daily`](#noaaghcn-daily) | GHCN-Daily Station Observations | noaa | http | temporal, variable |
| [`noaa:nexrad-level2`](#noaanexrad-level2) | NEXRAD Level II Radar | noaa | s3 | temporal |

## noaa:coastwatch-sst

**CoastWatch Sea Surface Temperature**

Gridded blended sea surface temperature from NOAA CoastWatch, served through ERDDAP with full server-side spatial, temporal, and variable subsetting.

- Homepage: https://coastwatch.noaa.gov/
- License: US Government Work (public domain)
- Extent: -180, -90, 180, 90
- Keywords: ocean, sst, sea surface temperature, satellite, erddap, coastwatch, gridded
- Adapter: `usdata.providers.noaa.coastwatch:CoastwatchSst`

## noaa:ghcn-daily

**GHCN-Daily Station Observations**

Global Historical Climatology Network daily summaries: temperature, precipitation, snow, and other elements from land surface stations, served by the NCEI Access Data Service with station and date filtering.

- Homepage: https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily
- License: US Government Work (public domain)
- Extent: -180, -90, 180, 90; 1763-01-01 to present
- Keywords: climate, weather, temperature, precipitation, snow, stations, daily, ghcn, ncei
- Adapter: `usdata.providers.noaa.ghcnd:GhcnDaily`

## noaa:nexrad-level2

**NEXRAD Level II Radar**

Raw volume scans from the WSR-88D weather radar network, archived in the public unidata-nexrad-level2 S3 bucket (NOAA Open Data Dissemination). One object per radar site per volume scan. No server-side subsetting; whole files are fetched. Select radars by site id, bbox, or nearest to a point.

- Homepage: https://registry.opendata.aws/noaa-nexrad/
- License: US Government Work (public domain)
- Extent: -180, 15, -60, 72; 1991-06-01 to present
- Keywords: radar, weather, storms, tornado, precipitation, reflectivity, nexrad, wsr-88d
- Adapter: `usdata.providers.noaa.nexrad:NexradLevel2`
