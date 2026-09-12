# NOAA datasets

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

[Provider access notes](../../providers/noaa.md).

**Released** is included in usdata 0.13.0. **Source only** is implemented in this checkout and requires a source installation. **Planned** cannot fetch data yet.

## Implemented datasets

| Dataset | Availability | Files | What gets selected |
|---|---|---|---|
| <span id="noaaghcn-daily"></span>[Daily station weather](noaa/ghcn-daily.md) | Released | CSV | Station observations within inclusive calendar dates; selected elements |
| <span id="noaagsom"></span>[Monthly station climate](noaa/gsom.md) | Released | CSV | Complete UTC calendar months touched by the query; station and element filters |
| <span id="noaagsoy"></span>[Annual station climate](noaa/gsoy.md) | Released | CSV | Complete UTC calendar years touched by the query; station and element filters |
| <span id="noaastorm-events"></span>[Storm Events details](noaa/storm-events.md) | Released | gzip CSV | Whole annual archives; filter rows locally after downloading |
| <span id="noaanexrad-level2"></span>[NEXRAD radar scans](noaa/nexrad-level2.md) | Released | NEXRAD Level II | Whole radar scans by site and inclusive UTC scan-start time |
| <span id="noaagoes-abi"></span>[GOES CONUS imagery](noaa/goes-abi.md) | Released | NetCDF4 | Whole single-channel CONUS scenes by inclusive UTC scan-start time |
| <span id="noaahurdat2"></span>[Tropical cyclone best tracks](noaa/hurdat2.md) | Released | HURDAT2 fixed-format text | The newest revision of one whole basin file; filter track points locally |
| <span id="noaaclimate-normals"></span>[30-year station climate normals](noaa/climate-normals.md) | Released | CSV | Monthly, daily, or annual/seasonal normals per station; optional month-day window for daily and monthly |
| <span id="noaacoops-water-levels"></span>[Coastal water levels](noaa/coops-water-levels.md) | Released | CSV | Six-minute observations for one station and datum; at most 28 days |
| <span id="noaacoastwatch-sst"></span>[Sea-surface temperature](noaa/coastwatch-sst.md) | Released | CSV with units row | Grid centers and timestamps inside the requested bounds; optional stride |

## Planned datasets

These entries are not implemented; they cannot fetch data.

### noaa:ghcn-hourly

**GHCN-Hourly Station Observations** · Planned · target later

Global hourly and sub-hourly surface observations, the successor to ISD. Published as per-station and per-year bulk files by NCEI; the exact access path has not been confirmed yet and must be verified before an adapter is built.

[Upstream information](https://www.ncei.noaa.gov/products/global-historical-climatology-network-hourly)
Domain: Surface weather.

### noaa:lcd

**Local Climatological Data** · Planned · target later

Hourly, daily, and monthly observations from airport and first-order stations via the NCEI Access Data Service dataset local-climatological-data, addressed by WBAN-based station ids.

[Upstream information](https://www.ncei.noaa.gov/products/land-based-station/local-climatological-data)
Domain: Surface weather.

### noaa:mrms

**Multi-Radar Multi-Sensor (MRMS)** · Planned · target later

Gridded CONUS products merged from all radars plus other sensors (reflectivity, precipitation rate and accumulation, severe weather diagnostics), as two-minute gzipped GRIB2 files in the public noaa-mrms-pds S3 bucket laid out as CONUS/PRODUCT/YYYYMMDD/.

[Upstream information](https://registry.opendata.aws/noaa-mrms-pds/)
Domain: Weather radar.

### noaa:nexrad-level3

**NEXRAD Level III Products** · Planned · target later

Derived single-radar products (base reflectivity, velocity, storm totals, and others) in the public unidata-nexrad-level3 S3 bucket, with flat keys SITE_PRODUCT_YYYY_MM_DD_HH_MM_SS where the site id drops its leading K. Recent data only; the archive is at NCEI.

[Upstream information](https://registry.opendata.aws/noaa-nexrad/)
Domain: Weather radar.

### noaa:goes-glm

**GOES Geostationary Lightning Mapper** · Planned · target later

Lightning flash, group, and event detections (GLM-L2-LCFA) in 20-second NetCDF files under the same GOES S3 buckets and layout as ABI.

[Upstream information](https://registry.opendata.aws/noaa-goes/)
Domain: Weather satellites.

### noaa:ibtracs

**IBTrACS Global Tropical Cyclone Tracks** · Planned · target later

International Best Track Archive for Climate Stewardship: merged best tracks from all agencies worldwide since 1842. CSV and NetCDF files by basin or period from an NCEI HTTPS directory (v04r01).

[Upstream information](https://www.ncei.noaa.gov/products/international-best-track-archive)
Domain: Tropical cyclones.

### noaa:gfs

**GFS Forecast Model Output** · Planned · target later

Global Forecast System output in GRIB2 from the public noaa-gfs-bdp-pds S3 bucket, laid out as gfs.YYYYMMDD/HH/atmos/ with files per resolution and forecast hour (for example pgrb2.0p25.fNNN).

[Upstream information](https://registry.opendata.aws/noaa-gfs-bdp-pds/)
Domain: Weather models.

### noaa:hrrr

**HRRR Forecast Model Output** · Planned · target later

High-Resolution Rapid Refresh 3 km hourly forecasts in GRIB2 from the public noaa-hrrr-bdp-pds S3 bucket, laid out as hrrr.YYYYMMDD/conus/ with one file per cycle and forecast hour. Large files; cycle and forecast-hour selection are essential.

[Upstream information](https://registry.opendata.aws/noaa-hrrr-pds/)
Domain: Weather models.

### noaa:nbm

**National Blend of Models** · Planned · target later

Statistically blended forecast guidance in GRIB2 from the public noaa-nbm-grib2-pds S3 bucket, laid out as blend.YYYYMMDD/HH/core/ with files per region and forecast hour.

[Upstream information](https://registry.opendata.aws/noaa-nbm/)
Domain: Weather models.

### noaa:nclimdiv

**nClimDiv Climate Divisional Data** · Planned · target later

Monthly temperature, precipitation, and drought indices for U.S. climate divisions, states, and regions since 1895, as fixed-width text files in an NCEI monitoring-content directory refreshed monthly.

[Upstream information](https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/)
Domain: Climate.

### noaa:sea-ice-index

**Sea Ice Index** · Planned · target later

Daily and monthly Arctic and Antarctic sea ice extent and concentration (NOAA@NSIDC G02135) as CSV, GeoTIFF, and shapefiles in an HTTPS directory hosted by NSIDC.

[Upstream information](https://nsidc.org/data/g02135)
Domain: Snow and ice.

### noaa:ersst

**ERSST Monthly Sea Surface Temperature** · Planned · target later

Extended Reconstructed SST v5: monthly global 2 degree analysis since 1854, one NetCDF per month in an NCEI HTTPS directory.

[Upstream information](https://www.ncei.noaa.gov/products/extended-reconstructed-sst)
Domain: Ocean physics.

### noaa:oisst

**OISST Daily Sea Surface Temperature** · Planned · target later

Optimum Interpolation SST v2.1: daily global 0.25 degree analysis since September 1981 as one NetCDF per day, from the NOAA CDR S3 bucket (data/v2.1/avhrr/YYYYMM/) or the NCEI HTTPS mirror.

[Upstream information](https://www.ncei.noaa.gov/products/optimum-interpolation-sst)
Domain: Ocean physics.

### noaa:ocads

**Ocean Carbon and Acidification Data System** · Planned · target later

Archived ocean carbon, pH, and related chemistry datasets (cruises, moorings, syntheses such as SOCAT and GLODAP) in an NCEI HTTPS directory organized by accession.

[Upstream information](https://www.ncei.noaa.gov/products/ocean-carbon-acidification-data-system)
Domain: Ocean chemistry.

### noaa:etopo

**ETOPO 2022 Global Relief** · Planned · target later

Global topography and bathymetry at 15, 30, and 60 arc-seconds as NetCDF and GeoTIFF tiles, served through the NCEI THREDDS catalog with OPeNDAP access; the THREDDS pattern.

[Upstream information](https://www.ncei.noaa.gov/products/etopo-global-relief-model)
Domain: Bathymetry and hydrography.

### noaa:tsunami-events

**Global Historical Tsunami Database** · Planned · target later

Tsunami source events and runup observations since 2100 BCE from NCEI, served as JSON by the HazEL hazard-service API with year, magnitude, and location filters.

[Upstream information](https://www.ngdc.noaa.gov/hazel/view/hazards/tsunami/event-search)
Domain: Natural hazards.

### noaa:paleo-search

**World Data Service for Paleoclimatology** · Planned · target later

Proxy climate records (tree rings, ice cores, sediments, corals) with a JSON study-search API from NCEI that returns study metadata and data file URLs filtered by data type, region, and time span.

[Upstream information](https://www.ncei.noaa.gov/products/paleoclimatology)
Domain: Paleoclimate.

### noaa:swpc-realtime

**SWPC Real-Time Space Weather Products** · Planned · target later

Planetary K index, solar wind, and other real-time indices as small JSON files from the Space Weather Prediction Center services host. Rolling recent windows only; historical archives live elsewhere.

[Upstream information](https://www.swpc.noaa.gov/products-and-data)
Domain: Space weather.

### noaa:cdr-ndvi

**NDVI Climate Data Record** · Planned · target later

Daily global normalized difference vegetation index from AVHRR and VIIRS since 1981, one NetCDF per day in the public noaa-cdr-ndvi-pds S3 bucket laid out as data/YYYY/.

[Upstream information](https://www.ncei.noaa.gov/products/climate-data-records/normalized-difference-vegetation-index)
Domain: Land and environment.
