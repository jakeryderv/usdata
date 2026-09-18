# NOAA datasets

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

[Provider access notes](../../providers/noaa.md).

**Released** is included in usdata 0.21.0. **Source only** is implemented in this checkout and requires a source installation. **Planned** cannot fetch data yet.

## Implemented datasets

| Dataset | Availability | Files | What gets selected |
|---|---|---|---|
| <span id="noaastorm-events"></span>[Storm Events details, fatalities, and locations](noaa/storm-events.md) | Released | gzip CSV | Whole annual archives of one table; filter rows locally after downloading |
| <span id="noaaspc-tornado-reports"></span>[SPC tornado, hail, and wind databases](noaa/spc-tornado-reports.md) | Released | CSV | Whole annual, half-decade, or decade files of one table; filter rows locally after downloading |
| <span id="noaanws-vtec-events"></span>[NWS warnings and watches by county](noaa/nws-vtec-events.md) | Source only | CSV | Events issued for one county or UGC inside an inclusive UTC window; optionally one event type |
| <span id="noaamrms"></span>[MRMS gridded radar products](noaa/mrms.md) | Released | GRIB2 (gzipped) | Whole two-minute CONUS grids of one product by inclusive UTC file stamp, at most one day |
| <span id="noaahurdat2"></span>[Tropical cyclone best tracks](noaa/hurdat2.md) | Released | HURDAT2 fixed-format text | The newest revision of one whole basin file; filter track points locally |
| <span id="noaaibtracs"></span>[Global tropical cyclone best tracks](noaa/ibtracs.md) | Released | CSV with a units row, NetCDF4 | One whole subset file per query, from the newest or a pinned product version |
| <span id="noaacoastwatch-sst"></span>[Sea-surface temperature](noaa/coastwatch-sst.md) | Released | CSV with units row | Grid centers and timestamps inside the requested bounds; optional stride |

### [NCEI Access Data Service](https://www.ncei.noaa.gov/support/access-data-service-api-user-documentation)

| Dataset | Availability | Files | What gets selected |
|---|---|---|---|
| <span id="noaaghcn-daily"></span>[Daily station weather](noaa/ghcn-daily.md) | Released | CSV | Station observations within inclusive calendar dates; selected elements |
| <span id="noaagsom"></span>[Monthly station climate](noaa/gsom.md) | Released | CSV | Complete UTC calendar months touched by the query; station and element filters |
| <span id="noaagsoy"></span>[Annual station climate](noaa/gsoy.md) | Released | CSV | Complete UTC calendar years touched by the query; station and element filters |
| <span id="noaalcd"></span>[Hourly airport observations](noaa/lcd.md) | Released | CSV | Every report on whole calendar days per station; optional column filters |
| <span id="noaaclimate-normals"></span>[30-year station climate normals](noaa/climate-normals.md) | Released | CSV | Monthly, daily, or annual/seasonal normals per station; optional month-day window for daily and monthly |

### [Next Generation Weather Radar (NEXRAD)](https://www.ncei.noaa.gov/products/radar/next-generation-weather-radar)

| Dataset | Availability | Files | What gets selected |
|---|---|---|---|
| <span id="noaanexrad-level2"></span>[NEXRAD radar scans](noaa/nexrad-level2.md) | Released | NEXRAD Level II | Whole radar scans by site and inclusive UTC scan-start time |
| <span id="noaanexrad-level3"></span>[NEXRAD derived radar products](noaa/nexrad-level3.md) | Released | NEXRAD Level III (no reader) | Whole product files by site, product code, and inclusive UTC scan time since 2020-03-30 |

### [GOES-R Series](https://www.goes-r.gov/)

| Dataset | Availability | Files | What gets selected |
|---|---|---|---|
| <span id="noaagoes-abi"></span>[GOES CONUS imagery](noaa/goes-abi.md) | Released | NetCDF4 | Whole single-channel CONUS scenes by inclusive UTC scan-start time |
| <span id="noaagoes-glm"></span>[GOES lightning detections](noaa/goes-glm.md) | Released | NetCDF4 | Whole 20-second detection files by inclusive UTC file-start time, at most one day |

### [NCEP model output](https://www.nco.ncep.noaa.gov/pmb/products/)

| Dataset | Availability | Files | What gets selected |
|---|---|---|---|
| <span id="noaagfs"></span>[GFS model output](noaa/gfs.md) | Released | GRIB2 | Global files, whole or by named GRIB2 message, chosen by run initialization window, cycle hour, forecast hours, and grid resolution |
| <span id="noaahrrr"></span>[HRRR model output](noaa/hrrr.md) | Released | GRIB2 | CONUS files, whole or by named GRIB2 message, chosen by run initialization window, cycle hour, forecast hours, and file variant |
| <span id="noaanbm"></span>[NBM forecast guidance](noaa/nbm.md) | Released | GRIB2 | Regional core files, whole or by named GRIB2 message, chosen by run initialization window, cycle hour, forecast hours, and region |
| <span id="noaarap"></span>[RAP model output](noaa/rap.md) | Released | GRIB2 | Files, whole or by named GRIB2 message, chosen by run initialization window, cycle hour, forecast hours, and file family |

### [CO-OPS Data API](https://tidesandcurrents.noaa.gov/)

| Dataset | Availability | Files | What gets selected |
|---|---|---|---|
| <span id="noaacoops-water-levels"></span>[Coastal water levels](noaa/coops-water-levels.md) | Released | CSV | Six-minute observations for one station and datum; at most 28 days |
| <span id="noaacoops-tide-predictions"></span>[Coastal tide predictions](noaa/coops-tide-predictions.md) | Released | CSV | Predictions for one station and datum on a chosen interval; at most a year |

## Planned datasets

These entries are not implemented; they cannot fetch data.

### noaa:ghcn-hourly

**GHCN-Hourly Station Observations** · Planned · target later

Global hourly and sub-hourly surface observations, the successor to ISD. Published as per-station and per-year bulk files by NCEI; the exact access path has not been confirmed yet and must be verified before an adapter is built.

[Upstream information](https://www.ncei.noaa.gov/products/global-historical-climatology-network-hourly)
Domain: Surface weather.

### noaa:igra

**IGRA Radiosonde Observations** · Planned · target later

Integrated Global Radiosonde Archive version 2: observed upper-air soundings from 2,931 stations as one zipped fixed-width text file per station for its full period of record (about 81 MB for Norman, Oklahoma), plus year-to-date and derived-parameter directories, from an NCEI HTTPS directory. Needs a fixed-width sounding reader.

[Upstream information](https://www.ncei.noaa.gov/products/weather-balloon/integrated-global-radiosonde-archive)
Domain: Surface weather.

### noaa:nws-warnings

**NWS Watch, Warning, and Advisory Archive** · Planned · target later

Every National Weather Service watch, warning, and advisory polygon with VTEC codes and issue, expiry, and update times, as one zipped shapefile per year. The maintained archive is the Iowa Environmental Mesonet's mirror of NWS products, not an NWS endpoint; the tornado and severe thunderstorm storm-based warnings for 2024 are 6.5 MB and all products 351 MB. Needs a shapefile reader.

[Upstream information](https://mesonet.agron.iastate.edu/request/gis/watchwarn.phtml)
Domain: Severe weather.

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

### noaa:billion-dollar-disasters

**Billion-Dollar Weather and Climate Disasters** · Planned · target later

NCEI's list of U.S. disasters with CPI-adjusted and unadjusted costs, dates, and deaths since 1980, served as one CSV with two header comment lines from the NCEI access service (about 36 kB for all events).

[Upstream information](https://www.ncei.noaa.gov/access/billions/)
Domain: Natural hazards.

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
