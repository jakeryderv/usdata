# Datasets

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

Status: **available** has a tested adapter, **stub** has an adapter class that is not implemented yet, **planned** is a registry entry only.

## NOAA

Provider id `noaa`. [NOAA](https://www.noaa.gov/).

| Dataset | Status | Description | Protocol | Server-side subsetting |
|---|---|---|---|---|
| [`noaa:ghcn-daily`](#noaaghcn-daily) | available | Global Historical Climatology Network daily summaries: temperature, precipitation, snow, and other elements from land surface stations, served by the NCEI Access Data Service with station and date filtering. | http | temporal, variable |
| [`noaa:nexrad-level2`](#noaanexrad-level2) | available | Raw volume scans from the WSR-88D weather radar network, archived in the public unidata-nexrad-level2 S3 bucket (NOAA Open Data Dissemination). | s3 | temporal |
| [`noaa:coastwatch-sst`](#noaacoastwatch-sst) | stub | Gridded blended sea surface temperature from NOAA CoastWatch, served through ERDDAP with full server-side spatial, temporal, and variable subsetting. | erddap | spatial, temporal, variable |
| [`noaa:goes-abi`](#noaagoes-abi) | planned | Advanced Baseline Imager Level 1b radiances and Level 2 products from GOES-16/18/19, published to public S3 buckets. | s3 | temporal, variable |

## Census Bureau

Provider id `census`. [Census Bureau](https://www.census.gov/).

| Dataset | Status | Description | Protocol | Server-side subsetting |
|---|---|---|---|---|
| [`census:acs-5year`](#censusacs-5year) | planned | Population, housing, income, and demographic estimates for every geography down to block group, via the Census Data API. | http | spatial, temporal, variable |

## EPA

Provider id `epa`. [EPA](https://www.epa.gov/).

| Dataset | Status | Description | Protocol | Server-side subsetting |
|---|---|---|---|---|
| [`epa:aqs-daily`](#epaaqs-daily) | planned | Daily pollutant summaries (ozone, PM2.5, NO2, and others) from regulatory monitors via the AQS Data API. | http | spatial, temporal, variable |

## FEMA

Provider id `fema`. [FEMA](https://www.fema.gov/).

| Dataset | Status | Description | Protocol | Server-side subsetting |
|---|---|---|---|---|
| [`fema:nfhl`](#femanfhl) | planned | Effective flood zones, base flood elevations, and related features from FEMA's flood insurance rate maps, available as county or state extracts and through ArcGIS services. | http | spatial |

## NASA

Provider id `nasa`. [NASA](https://www.earthdata.nasa.gov/).

| Dataset | Status | Description | Protocol | Server-side subsetting |
|---|---|---|---|---|
| [`nasa:gpm-imerg`](#nasagpm-imerg) | planned | Global half-hourly and daily merged satellite precipitation estimates. | http | temporal |

## USDA

Provider id `usda`. [USDA](https://www.usda.gov/).

| Dataset | Status | Description | Protocol | Server-side subsetting |
|---|---|---|---|---|
| [`usda:cropland-data-layer`](#usdacropland-data-layer) | planned | Annual 30 m raster of crop type across the contiguous United States from NASS, served through CropScape with bbox extraction. | http | spatial, temporal |

## USGS

Provider id `usgs`. [USGS](https://www.usgs.gov/).

| Dataset | Status | Description | Protocol | Server-side subsetting |
|---|---|---|---|---|
| [`usgs:3dep-elevation`](#usgs3dep-elevation) | planned | Seamless digital elevation models from the 3D Elevation Program (1/3 arc-second and 1 m where available). | s3 | spatial |
| [`usgs:earthquakes`](#usgsearthquakes) | planned | Global earthquake events with location, magnitude, and depth from the ANSS Comprehensive Catalog via the FDSN event web service. | http | spatial, temporal |
| [`usgs:water-daily`](#usgswater-daily) | planned | Daily statistics (streamflow, gage height, temperature) for USGS monitoring sites. | http | spatial, temporal, variable |

---

# Dataset details

## noaa:ghcn-daily

**GHCN-Daily Station Observations** · available

Global Historical Climatology Network daily summaries: temperature, precipitation, snow, and other elements from land surface stations, served by the NCEI Access Data Service with station and date filtering.

- Homepage: https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily
- License: US Government Work (public domain)
- Extent: -180, -90, 180, 90; 1763-01-01 to present
- Keywords: climate, weather, temperature, precipitation, snow, stations, daily, ghcn, ncei
- Adapter: `usdata.providers.noaa.ghcnd:GhcnDaily`

## noaa:nexrad-level2

**NEXRAD Level II Radar** · available

Raw volume scans from the WSR-88D weather radar network, archived in the public unidata-nexrad-level2 S3 bucket (NOAA Open Data Dissemination). One object per radar site per volume scan. No server-side subsetting; whole files are fetched. Select radars by site id, bbox, or nearest to a point.

- Homepage: https://registry.opendata.aws/noaa-nexrad/
- License: US Government Work (public domain)
- Extent: -180, 15, -60, 72; 1991-06-01 to present
- Keywords: radar, weather, storms, tornado, precipitation, reflectivity, nexrad, wsr-88d
- Adapter: `usdata.providers.noaa.nexrad:NexradLevel2`

## noaa:coastwatch-sst

**CoastWatch Sea Surface Temperature** · stub

Gridded blended sea surface temperature from NOAA CoastWatch, served through ERDDAP with full server-side spatial, temporal, and variable subsetting.

- Homepage: https://coastwatch.noaa.gov/
- License: US Government Work (public domain)
- Extent: -180, -90, 180, 90
- Keywords: ocean, sst, sea surface temperature, satellite, erddap, coastwatch, gridded
- Adapter: `usdata.providers.noaa.coastwatch:CoastwatchSst`

## noaa:goes-abi

**GOES-R ABI Satellite Imagery** · planned

Advanced Baseline Imager Level 1b radiances and Level 2 products from GOES-16/18/19, published to public S3 buckets. Same anonymous S3 access pattern as NEXRAD; whole files per product per scan.

- Homepage: https://registry.opendata.aws/noaa-goes/
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: satellite, imagery, goes, abi, clouds, fire, radiance
- Adapter: none yet

## census:acs-5year

**American Community Survey 5-Year Estimates** · planned

Population, housing, income, and demographic estimates for every geography down to block group, via the Census Data API. Anonymous for light use; an API key lifts rate limits.

- Homepage: https://www.census.gov/data/developers/data-sets/acs-5year.html
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: population, demographics, housing, income, acs, census
- Adapter: none yet

## epa:aqs-daily

**Air Quality System Daily Summaries** · planned

Daily pollutant summaries (ozone, PM2.5, NO2, and others) from regulatory monitors via the AQS Data API. Requires a free API key issued by email.

- Homepage: https://aqs.epa.gov/aqsweb/documents/data_api.html
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: air quality, pollution, ozone, pm2.5, monitors, aqs
- Adapter: none yet

## fema:nfhl

**National Flood Hazard Layer** · planned

Effective flood zones, base flood elevations, and related features from FEMA's flood insurance rate maps, available as county or state extracts and through ArcGIS services.

- Homepage: https://www.fema.gov/flood-maps/national-flood-hazard-layer
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: flood, hazards, floodplain, insurance, firm, nfhl
- Adapter: none yet

## nasa:gpm-imerg

**GPM IMERG Precipitation** · planned

Global half-hourly and daily merged satellite precipitation estimates. Discovered through NASA CMR and downloaded from GES DISC. Requires a free Earthdata Login; the first credentialed dataset.

- Homepage: https://gpm.nasa.gov/data/imerg
- License: NASA open data
- Extent: not stated
- Keywords: precipitation, rainfall, satellite, gpm, imerg, climate
- Adapter: none yet

## usda:cropland-data-layer

**Cropland Data Layer** · planned

Annual 30 m raster of crop type across the contiguous United States from NASS, served through CropScape with bbox extraction.

- Homepage: https://www.nass.usda.gov/Research_and_Science/Cropland/SARS1a.php
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: agriculture, crops, land cover, raster, nass, cdl
- Adapter: none yet

## usgs:3dep-elevation

**3DEP Elevation** · planned

Seamless digital elevation models from the 3D Elevation Program (1/3 arc-second and 1 m where available). Tiled rasters on public cloud storage; spatial selection by tile.

- Homepage: https://www.usgs.gov/3d-elevation-program
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: elevation, dem, terrain, lidar, 3dep, topography
- Adapter: none yet

## usgs:earthquakes

**Earthquake Catalog (ComCat)** · planned

Global earthquake events with location, magnitude, and depth from the ANSS Comprehensive Catalog via the FDSN event web service. Anonymous REST with bbox, time, and magnitude filters.

- Homepage: https://earthquake.usgs.gov/fdsnws/event/1/
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: earthquakes, seismic, geology, hazards, comcat, fdsn
- Adapter: none yet

## usgs:water-daily

**Streamflow and Water Daily Values** · planned

Daily statistics (streamflow, gage height, temperature) for USGS monitoring sites. The legacy NWIS web services are being replaced by the USGS Water Data APIs; the adapter must target whichever is current.

- Homepage: https://api.waterdata.usgs.gov/
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: water, streamflow, discharge, rivers, gages, hydrology, nwis
- Adapter: none yet
