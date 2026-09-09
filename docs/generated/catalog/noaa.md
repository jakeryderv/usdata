# NOAA dataset catalog

[Provider access notes](../../providers/noaa.md). Status describes this source checkout; see version labels for release support.

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

| Dataset | Domain | Status | Version | Description | Protocol |
|---|---|---|---|---|---|
| [`noaa:ghcn-daily`](#noaaghcn-daily) | Surface weather | available | since 0.2 | Global Historical Climatology Network daily summaries: temperature, precipitation, snow, and other elements from land surface stations, served by the NCEI Access Data Service with station and date filtering. | http |
| [`noaa:gsom`](#noaagsom) | Surface weather | available | since 0.7 | Monthly station summaries derived from GHCN-Daily (means, extremes, totals) via the NCEI Access Data Service dataset global-summary-of-the-month. | http |
| [`noaa:ghcn-hourly`](#noaaghcn-hourly) | Surface weather | planned | target later | Global hourly and sub-hourly surface observations, the successor to ISD. | http |
| [`noaa:gsoy`](#noaagsoy) | Surface weather | planned | target later | Annual station summaries derived from GHCN-Daily via the NCEI Access Data Service dataset global-summary-of-the-year. | http |
| [`noaa:lcd`](#noaalcd) | Surface weather | planned | target later | Hourly, daily, and monthly observations from airport and first-order stations via the NCEI Access Data Service dataset local-climatological-data, addressed by WBAN-based station ids. | http |
| [`noaa:storm-events`](#noaastorm-events) | Severe weather | available | since 0.8 | NCEI's significant-weather event details since 1950, with locations, impacts, and narratives. | http |
| [`noaa:nexrad-level2`](#noaanexrad-level2) | Weather radar | available | since 0.2 | Raw volume scans from the WSR-88D weather radar network, archived in the public unidata-nexrad-level2 S3 bucket (NOAA Open Data Dissemination). | s3 |
| [`noaa:mrms`](#noaamrms) | Weather radar | planned | target later | Gridded CONUS products merged from all radars plus other sensors (reflectivity, precipitation rate and accumulation, severe weather diagnostics), as two-minute gzipped GRIB2 files in the public noaa-mrms-pds S3 bucket laid out as CONUS/PRODUCT/YYYYMMDD/. | s3 |
| [`noaa:nexrad-level3`](#noaanexrad-level3) | Weather radar | planned | target later | Derived single-radar products (base reflectivity, velocity, storm totals, and others) in the public unidata-nexrad-level3 S3 bucket, with flat keys SITE_PRODUCT_YYYY_MM_DD_HH_MM_SS where the site id drops its leading K. | s3 |
| [`noaa:goes-abi`](#noaagoes-abi) | Weather satellites | available | since 0.8 | Single-channel CONUS Cloud and Moisture Imagery (ABI-L2-CMIPC) from GOES-16, 17, 18, and 19 in anonymous NOAA S3 buckets. | s3 |
| [`noaa:goes-glm`](#noaagoes-glm) | Weather satellites | planned | target later | Lightning flash, group, and event detections (GLM-L2-LCFA) in 20-second NetCDF files under the same GOES S3 buckets and layout as ABI. | s3 |
| [`noaa:hurdat2`](#noaahurdat2) | Tropical cyclones | planned | target later | National Hurricane Center best-track database: six-hourly position, intensity, pressure, and wind radii for Atlantic (since 1851) and eastern North Pacific (since 1949) tropical cyclones. | http |
| [`noaa:ibtracs`](#noaaibtracs) | Tropical cyclones | planned | target later | International Best Track Archive for Climate Stewardship: merged best tracks from all agencies worldwide since 1842. | http |
| [`noaa:gfs`](#noaagfs) | Weather models | planned | target later | Global Forecast System output in GRIB2 from the public noaa-gfs-bdp-pds S3 bucket, laid out as gfs.YYYYMMDD/HH/atmos/ with files per resolution and forecast hour (for example pgrb2.0p25.fNNN). | s3 |
| [`noaa:hrrr`](#noaahrrr) | Weather models | planned | target later | High-Resolution Rapid Refresh 3 km hourly forecasts in GRIB2 from the public noaa-hrrr-bdp-pds S3 bucket, laid out as hrrr.YYYYMMDD/conus/ with one file per cycle and forecast hour. | s3 |
| [`noaa:nbm`](#noaanbm) | Weather models | planned | target later | Statistically blended forecast guidance in GRIB2 from the public noaa-nbm-grib2-pds S3 bucket, laid out as blend.YYYYMMDD/HH/core/ with files per region and forecast hour. | s3 |
| [`noaa:climate-normals`](#noaaclimate-normals) | Climate | planned | target later | Daily and monthly station normals via the NCEI Access Data Service datasets normals-daily-1991-2020 and normals-monthly-1991-2020. | http |
| [`noaa:nclimdiv`](#noaanclimdiv) | Climate | planned | target later | Monthly temperature, precipitation, and drought indices for U.S. | http |
| [`noaa:sea-ice-index`](#noaasea-ice-index) | Snow and ice | planned | target later | Daily and monthly Arctic and Antarctic sea ice extent and concentration (NOAA@NSIDC G02135) as CSV, GeoTIFF, and shapefiles in an HTTPS directory hosted by NSIDC. | http |
| [`noaa:ersst`](#noaaersst) | Ocean physics | planned | target later | Extended Reconstructed SST v5: monthly global 2 degree analysis since 1854, one NetCDF per month in an NCEI HTTPS directory. | http |
| [`noaa:oisst`](#noaaoisst) | Ocean physics | planned | target later | Optimum Interpolation SST v2.1: daily global 0.25 degree analysis since September 1981 as one NetCDF per day, from the NOAA CDR S3 bucket (data/v2.1/avhrr/YYYYMM/) or the NCEI HTTPS mirror. | s3 |
| [`noaa:coops-water-levels`](#noaacoops-water-levels) | Sea level and tides | available | unreleased; planned 0.10 | Preliminary or verified six-minute observed water levels from the anonymous CO-OPS Data API. | http |
| [`noaa:ocads`](#noaaocads) | Ocean chemistry | planned | target later | Archived ocean carbon, pH, and related chemistry datasets (cruises, moorings, syntheses such as SOCAT and GLODAP) in an NCEI HTTPS directory organized by accession. | http |
| [`noaa:coastwatch-sst`](#noaacoastwatch-sst) | Satellite oceanography | available | since 0.5 | NOAA geo-polar blended daily SST analysis (day and night) on a global 5 km grid, ERDDAP dataset noaacwBLENDEDsstDNDaily on the CoastWatch server, with server-side spatial, temporal, and variable subsetting. | erddap |
| [`noaa:etopo`](#noaaetopo) | Bathymetry and hydrography | planned | target later | Global topography and bathymetry at 15, 30, and 60 arc-seconds as NetCDF and GeoTIFF tiles, served through the NCEI THREDDS catalog with OPeNDAP access; the THREDDS pattern. | thredds |
| [`noaa:tsunami-events`](#noaatsunami-events) | Natural hazards | planned | target later | Tsunami source events and runup observations since 2100 BCE from NCEI, served as JSON by the HazEL hazard-service API with year, magnitude, and location filters. | http |
| [`noaa:paleo-search`](#noaapaleo-search) | Paleoclimate | planned | target later | Proxy climate records (tree rings, ice cores, sediments, corals) with a JSON study-search API from NCEI that returns study metadata and data file URLs filtered by data type, region, and time span. | http |
| [`noaa:swpc-realtime`](#noaaswpc-realtime) | Space weather | planned | target later | Planetary K index, solar wind, and other real-time indices as small JSON files from the Space Weather Prediction Center services host. | http |
| [`noaa:cdr-ndvi`](#noaacdr-ndvi) | Land and environment | planned | target later | Daily global normalized difference vegetation index from AVHRR and VIIRS since 1981, one NetCDF per day in the public noaa-cdr-ndvi-pds S3 bucket laid out as data/YYYY/. | s3 |

### noaa:ghcn-daily

**GHCN-Daily Station Observations** · available · since 0.2

Global Historical Climatology Network daily summaries: temperature, precipitation, snow, and other elements from land surface stations, served by the NCEI Access Data Service with station and date filtering.

- Domain: Surface weather
- Server-side subsetting: temporal, variable
- Homepage: https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily
- License: US Government Work (public domain)
- Extent: -180, -90, 180, 90; 1763-01-01 to present
- Keywords: climate, weather, temperature, precipitation, snow, stations, daily, ghcn, ncei
- Adapter: `usdata.providers.noaa.ghcnd:GhcnDaily`

### noaa:gsom

**Global Summary of the Month** · available · since 0.7

Monthly station summaries derived from GHCN-Daily (means, extremes, totals) via the NCEI Access Data Service dataset global-summary-of-the-month. Selects whole calendar months and explicit stations, or discovers stations through the companion search service.

- Domain: Surface weather
- Server-side subsetting: temporal, variable
- Homepage: https://www.ncei.noaa.gov/access/search/data-search/global-summary-of-the-month
- License: US Government Work (public domain)
- Extent: -180, -90, 180, 90
- Keywords: climate, monthly, stations, temperature, precipitation, gsom, ncei
- Adapter: `usdata.providers.noaa.gsom:GlobalSummaryMonthly`

### noaa:ghcn-hourly

**GHCN-Hourly Station Observations** · planned · target later

Global hourly and sub-hourly surface observations, the successor to ISD. Published as per-station and per-year bulk files by NCEI; the exact access path has not been confirmed yet and must be verified before an adapter is built.

- Domain: Surface weather
- Server-side subsetting: temporal
- Homepage: https://www.ncei.noaa.gov/products/global-historical-climatology-network-hourly
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: weather, hourly, stations, global, ghcnh, ncei
- Adapter: none yet

### noaa:gsoy

**Global Summary of the Year** · planned · target later

Annual station summaries derived from GHCN-Daily via the NCEI Access Data Service dataset global-summary-of-the-year. Shares the GHCN-Daily client.

- Domain: Surface weather
- Server-side subsetting: temporal, variable
- Homepage: https://www.ncei.noaa.gov/access/search/data-search/global-summary-of-the-year
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: climate, annual, stations, temperature, precipitation, gsoy, ncei
- Adapter: none yet

### noaa:lcd

**Local Climatological Data** · planned · target later

Hourly, daily, and monthly observations from airport and first-order stations via the NCEI Access Data Service dataset local-climatological-data, addressed by WBAN-based station ids.

- Domain: Surface weather
- Server-side subsetting: temporal, variable
- Homepage: https://www.ncei.noaa.gov/products/land-based-station/local-climatological-data
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: weather, hourly, airports, stations, lcd, ncei
- Adapter: none yet

### noaa:storm-events

**Storm Events Database** · available · since 0.8

NCEI's significant-weather event details since 1950, with locations, impacts, and narratives. Anonymous whole-year gzipped CSV archives; select the latest creation-date revision for each requested year. No server-side row, location, or variable subsetting. Historical event coverage and reporting practices vary; fatalities and locations tables are separate products not included by this adapter.

- Domain: Severe weather
- Server-side subsetting: none
- Homepage: https://www.ncei.noaa.gov/access/storm-events-database/
- License: US Government Work (public domain)
- Extent: 1950-01-01 to present
- Keywords: storms, tornado, hail, wind, flood, damage, severe weather, events
- Adapter: `usdata.providers.noaa.storm_events:StormEvents`

### noaa:nexrad-level2

**NEXRAD Level II Radar** · available · since 0.2

Raw volume scans from the WSR-88D weather radar network, archived in the public unidata-nexrad-level2 S3 bucket (NOAA Open Data Dissemination). One object per radar site per volume scan. No server-side subsetting; whole files are fetched. Select radars by site id, bbox, or nearest to a point.

- Domain: Weather radar
- Server-side subsetting: temporal
- Homepage: https://registry.opendata.aws/noaa-nexrad/
- License: US Government Work (public domain)
- Extent: -180, 15, -60, 72; 1991-06-01 to present
- Keywords: radar, weather, storms, tornado, precipitation, reflectivity, nexrad, wsr-88d
- Adapter: `usdata.providers.noaa.nexrad:NexradLevel2`

### noaa:mrms

**Multi-Radar Multi-Sensor (MRMS)** · planned · target later

Gridded CONUS products merged from all radars plus other sensors (reflectivity, precipitation rate and accumulation, severe weather diagnostics), as two-minute gzipped GRIB2 files in the public noaa-mrms-pds S3 bucket laid out as CONUS/PRODUCT/YYYYMMDD/.

- Domain: Weather radar
- Server-side subsetting: temporal, variable
- Homepage: https://registry.opendata.aws/noaa-mrms-pds/
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: radar, mrms, precipitation, reflectivity, gridded, grib2, conus
- Adapter: none yet

### noaa:nexrad-level3

**NEXRAD Level III Products** · planned · target later

Derived single-radar products (base reflectivity, velocity, storm totals, and others) in the public unidata-nexrad-level3 S3 bucket, with flat keys SITE_PRODUCT_YYYY_MM_DD_HH_MM_SS where the site id drops its leading K. Recent data only; the archive is at NCEI.

- Domain: Weather radar
- Server-side subsetting: temporal, variable
- Homepage: https://registry.opendata.aws/noaa-nexrad/
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: radar, nexrad, level iii, reflectivity, velocity, products
- Adapter: none yet

### noaa:goes-abi

**GOES-R ABI CONUS Cloud and Moisture Imagery** · available · since 0.8

Single-channel CONUS Cloud and Moisture Imagery (ABI-L2-CMIPC) from GOES-16, 17, 18, and 19 in anonymous NOAA S3 buckets. Select an explicit satellite, channel, and scan-start interval; each asset is a complete NetCDF scene with no geographic or variable subsetting.

- Domain: Weather satellites
- Server-side subsetting: temporal
- Homepage: https://registry.opendata.aws/noaa-goes/
- License: US Government Work (public domain)
- Extent: 2017-02-28 to present
- Keywords: satellite, imagery, goes, abi, clouds, infrared, reflectance, netcdf, conus
- Adapter: `usdata.providers.noaa.goes:GoesAbi`

### noaa:goes-glm

**GOES Geostationary Lightning Mapper** · planned · target later

Lightning flash, group, and event detections (GLM-L2-LCFA) in 20-second NetCDF files under the same GOES S3 buckets and layout as ABI.

- Domain: Weather satellites
- Server-side subsetting: temporal
- Homepage: https://registry.opendata.aws/noaa-goes/
- License: US Government Work (public domain)
- Extent: 2017-01-01 to present
- Keywords: lightning, glm, goes, satellite, storms
- Adapter: none yet

### noaa:hurdat2

**HURDAT2 Atlantic and Pacific Best Tracks** · planned · target later

National Hurricane Center best-track database: six-hourly position, intensity, pressure, and wind radii for Atlantic (since 1851) and eastern North Pacific (since 1949) tropical cyclones. One fixed-format text file per basin, refreshed each season; the single-file pattern.

- Domain: Tropical cyclones
- Server-side subsetting: none
- Homepage: https://www.nhc.noaa.gov/data/#hurdat
- License: US Government Work (public domain)
- Extent: 1851-01-01 to present
- Keywords: hurricane, tropical cyclone, best track, nhc, atlantic, pacific
- Adapter: none yet

### noaa:ibtracs

**IBTrACS Global Tropical Cyclone Tracks** · planned · target later

International Best Track Archive for Climate Stewardship: merged best tracks from all agencies worldwide since 1842. CSV and NetCDF files by basin or period from an NCEI HTTPS directory (v04r01).

- Domain: Tropical cyclones
- Server-side subsetting: none
- Homepage: https://www.ncei.noaa.gov/products/international-best-track-archive
- License: US Government Work (public domain)
- Extent: 1842-01-01 to present
- Keywords: tropical cyclone, hurricane, typhoon, best track, ibtracs, global
- Adapter: none yet

### noaa:gfs

**GFS Forecast Model Output** · planned · target later

Global Forecast System output in GRIB2 from the public noaa-gfs-bdp-pds S3 bucket, laid out as gfs.YYYYMMDD/HH/atmos/ with files per resolution and forecast hour (for example pgrb2.0p25.fNNN).

- Domain: Weather models
- Server-side subsetting: temporal
- Homepage: https://registry.opendata.aws/noaa-gfs-bdp-pds/
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: forecast, model, gfs, grib2, global, nwp
- Adapter: none yet

### noaa:hrrr

**HRRR Forecast Model Output** · planned · target later

High-Resolution Rapid Refresh 3 km hourly forecasts in GRIB2 from the public noaa-hrrr-bdp-pds S3 bucket, laid out as hrrr.YYYYMMDD/conus/ with one file per cycle and forecast hour. Large files; cycle and forecast-hour selection are essential.

- Domain: Weather models
- Server-side subsetting: temporal
- Homepage: https://registry.opendata.aws/noaa-hrrr-pds/
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: forecast, model, hrrr, grib2, weather, nwp
- Adapter: none yet

### noaa:nbm

**National Blend of Models** · planned · target later

Statistically blended forecast guidance in GRIB2 from the public noaa-nbm-grib2-pds S3 bucket, laid out as blend.YYYYMMDD/HH/core/ with files per region and forecast hour.

- Domain: Weather models
- Server-side subsetting: temporal
- Homepage: https://registry.opendata.aws/noaa-nbm/
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: forecast, blend, nbm, grib2, guidance
- Adapter: none yet

### noaa:climate-normals

**U.S. Climate Normals 1991-2020** · planned · target later

Daily and monthly station normals via the NCEI Access Data Service datasets normals-daily-1991-2020 and normals-monthly-1991-2020. The daily dataset requires start and end dates inside a placeholder year (for example 2010-01-01 to 2010-12-31).

- Domain: Climate
- Server-side subsetting: temporal, variable
- Homepage: https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: climate, normals, averages, stations, temperature, precipitation
- Adapter: none yet

### noaa:nclimdiv

**nClimDiv Climate Divisional Data** · planned · target later

Monthly temperature, precipitation, and drought indices for U.S. climate divisions, states, and regions since 1895, as fixed-width text files in an NCEI monitoring-content directory refreshed monthly.

- Domain: Climate
- Server-side subsetting: none
- Homepage: https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/
- License: US Government Work (public domain)
- Extent: 1895-01-01 to present
- Keywords: climate, divisions, drought, temperature, precipitation, nclimdiv, monthly
- Adapter: none yet

### noaa:sea-ice-index

**Sea Ice Index** · planned · target later

Daily and monthly Arctic and Antarctic sea ice extent and concentration (NOAA@NSIDC G02135) as CSV, GeoTIFF, and shapefiles in an HTTPS directory hosted by NSIDC.

- Domain: Snow and ice
- Server-side subsetting: temporal
- Homepage: https://nsidc.org/data/g02135
- License: US Government Work (public domain)
- Extent: 1978-10-26 to present
- Keywords: sea ice, arctic, antarctic, extent, concentration, nsidc, polar
- Adapter: none yet

### noaa:ersst

**ERSST Monthly Sea Surface Temperature** · planned · target later

Extended Reconstructed SST v5: monthly global 2 degree analysis since 1854, one NetCDF per month in an NCEI HTTPS directory.

- Domain: Ocean physics
- Server-side subsetting: temporal
- Homepage: https://www.ncei.noaa.gov/products/extended-reconstructed-sst
- License: US Government Work (public domain)
- Extent: 1854-01-01 to present
- Keywords: sst, sea surface temperature, ocean, climate, ersst, monthly, netcdf
- Adapter: none yet

### noaa:oisst

**OISST Daily Sea Surface Temperature** · planned · target later

Optimum Interpolation SST v2.1: daily global 0.25 degree analysis since September 1981 as one NetCDF per day, from the NOAA CDR S3 bucket (data/v2.1/avhrr/YYYYMM/) or the NCEI HTTPS mirror.

- Domain: Ocean physics
- Server-side subsetting: temporal
- Homepage: https://www.ncei.noaa.gov/products/optimum-interpolation-sst
- License: US Government Work (public domain)
- Extent: 1981-09-01 to present
- Keywords: sst, sea surface temperature, ocean, climate data record, oisst, netcdf
- Adapter: none yet

### noaa:coops-water-levels

**CO-OPS Observed Water Levels** · available · unreleased; planned 0.10

Preliminary or verified six-minute observed water levels from the anonymous CO-OPS Data API. Select one station, an explicit vertical datum, units, and a UTC interval of at most 28 days. Raw CSV retains quality flags; predictions and station discovery are not included.

- Domain: Sea level and tides
- Server-side subsetting: temporal
- Homepage: https://api.tidesandcurrents.noaa.gov/api/prod/
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: tides, water level, sea level, coastal, coops, nwlon, stations
- Adapter: `usdata.providers.noaa.coops:CoopsWaterLevels`

### noaa:ocads

**Ocean Carbon and Acidification Data System** · planned · target later

Archived ocean carbon, pH, and related chemistry datasets (cruises, moorings, syntheses such as SOCAT and GLODAP) in an NCEI HTTPS directory organized by accession.

- Domain: Ocean chemistry
- Server-side subsetting: none
- Homepage: https://www.ncei.noaa.gov/products/ocean-carbon-acidification-data-system
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: ocean, carbon, acidification, ph, chemistry, ocads, socat
- Adapter: none yet

### noaa:coastwatch-sst

**CoastWatch Blended Sea Surface Temperature** · available · since 0.5

NOAA geo-polar blended daily SST analysis (day and night) on a global 5 km grid, ERDDAP dataset noaacwBLENDEDsstDNDaily on the CoastWatch server, with server-side spatial, temporal, and variable subsetting. Raw CSV subsets retain grid coordinates and units without volatile NetCDF history.

- Domain: Satellite oceanography
- Server-side subsetting: spatial, temporal, variable
- Homepage: https://coastwatch.noaa.gov/erddap/griddap/noaacwBLENDEDsstDNDaily.html
- License: GHRSST free and open data
- Extent: -179.975, -89.975, 179.975, 89.975; 2019-07-22 to present
- Keywords: ocean, sst, sea surface temperature, satellite, erddap, coastwatch, gridded, blended
- Adapter: `usdata.providers.noaa.coastwatch:CoastwatchSst`

### noaa:etopo

**ETOPO 2022 Global Relief** · planned · target later

Global topography and bathymetry at 15, 30, and 60 arc-seconds as NetCDF and GeoTIFF tiles, served through the NCEI THREDDS catalog with OPeNDAP access; the THREDDS pattern.

- Domain: Bathymetry and hydrography
- Server-side subsetting: spatial, variable
- Homepage: https://www.ncei.noaa.gov/products/etopo-global-relief-model
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: bathymetry, topography, elevation, relief, dem, etopo, global
- Adapter: none yet

### noaa:tsunami-events

**Global Historical Tsunami Database** · planned · target later

Tsunami source events and runup observations since 2100 BCE from NCEI, served as JSON by the HazEL hazard-service API with year, magnitude, and location filters.

- Domain: Natural hazards
- Server-side subsetting: spatial, temporal
- Homepage: https://www.ngdc.noaa.gov/hazel/view/hazards/tsunami/event-search
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: tsunami, hazards, earthquakes, historical, hazel, ncei
- Adapter: none yet

### noaa:paleo-search

**World Data Service for Paleoclimatology** · planned · target later

Proxy climate records (tree rings, ice cores, sediments, corals) with a JSON study-search API from NCEI that returns study metadata and data file URLs filtered by data type, region, and time span.

- Domain: Paleoclimate
- Server-side subsetting: spatial, temporal
- Homepage: https://www.ncei.noaa.gov/products/paleoclimatology
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: paleoclimate, proxies, tree rings, ice cores, sediments, corals
- Adapter: none yet

### noaa:swpc-realtime

**SWPC Real-Time Space Weather Products** · planned · target later

Planetary K index, solar wind, and other real-time indices as small JSON files from the Space Weather Prediction Center services host. Rolling recent windows only; historical archives live elsewhere.

- Domain: Space weather
- Server-side subsetting: variable
- Homepage: https://www.swpc.noaa.gov/products-and-data
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: space weather, solar wind, geomagnetic, kp index, swpc
- Adapter: none yet

### noaa:cdr-ndvi

**NDVI Climate Data Record** · planned · target later

Daily global normalized difference vegetation index from AVHRR and VIIRS since 1981, one NetCDF per day in the public noaa-cdr-ndvi-pds S3 bucket laid out as data/YYYY/.

- Domain: Land and environment
- Server-side subsetting: temporal
- Homepage: https://www.ncei.noaa.gov/products/climate-data-records/normalized-difference-vegetation-index
- License: US Government Work (public domain)
- Extent: 1981-06-24 to present
- Keywords: vegetation, ndvi, land, climate data record, avhrr, viirs
- Adapter: none yet
