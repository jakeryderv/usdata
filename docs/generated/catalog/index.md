# Find a dataset

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

**Released** is included in usdata 0.25.0. **Source only** is implemented in this checkout and requires a source installation. **Planned** cannot fetch data yet.

## Implemented datasets

| Dataset | Availability | Files | What gets selected |
|---|---|---|---|
| <span id="noaaghcn-daily"></span>[Daily station weather](noaa/ghcn-daily.md) | Released | CSV | Station observations within inclusive calendar dates; selected elements |
| <span id="noaagsom"></span>[Monthly station climate](noaa/gsom.md) | Released | CSV | Complete UTC calendar months touched by the query; station and element filters |
| <span id="noaagsoy"></span>[Annual station climate](noaa/gsoy.md) | Released | CSV | Complete UTC calendar years touched by the query; station and element filters |
| <span id="noaalcd"></span>[Hourly airport observations](noaa/lcd.md) | Released | CSV | Every report on whole calendar days per station; optional column filters |
| <span id="noaastorm-events"></span>[Storm Events details, fatalities, and locations](noaa/storm-events.md) | Released | gzip CSV | Whole annual archives of one table; filter rows locally after downloading |
| <span id="noaaspc-tornado-reports"></span>[SPC tornado, hail, and wind databases](noaa/spc-tornado-reports.md) | Released | CSV | Whole annual, half-decade, or decade files of one table; filter rows locally after downloading |
| <span id="noaanws-vtec-events"></span>[NWS warnings and watches by county](noaa/nws-vtec-events.md) | Released | CSV | Events issued for one county or UGC inside an inclusive UTC window; optionally one event type |
| <span id="noaanexrad-level2"></span>[NEXRAD radar scans](noaa/nexrad-level2.md) | Released | NEXRAD Level II | Whole radar scans by site and inclusive UTC scan-start time |
| <span id="noaamrms"></span>[MRMS gridded radar products](noaa/mrms.md) | Released | GRIB2 (gzipped) | Whole two-minute CONUS grids of one product by inclusive UTC file stamp, at most one day |
| <span id="noaanexrad-level3"></span>[NEXRAD derived radar products](noaa/nexrad-level3.md) | Released | NEXRAD Level III (no reader) | Whole product files by site, product code, and inclusive UTC scan time since 2020-03-30 |
| <span id="noaagoes-abi"></span>[GOES CONUS and mesoscale imagery](noaa/goes-abi.md) | Released | NetCDF4 | Whole single-channel scenes by inclusive UTC scan-start time and explicit mesoscale sector |
| <span id="noaagoes-glm"></span>[GOES lightning detections](noaa/goes-glm.md) | Released | NetCDF4 | Whole 20-second detection files by inclusive UTC file-start time, at most one day |
| <span id="noaahurdat2"></span>[Tropical cyclone best tracks](noaa/hurdat2.md) | Released | HURDAT2 fixed-format text | The newest revision of one whole basin file; filter track points locally |
| <span id="noaaibtracs"></span>[Global tropical cyclone best tracks](noaa/ibtracs.md) | Released | CSV with a units row, NetCDF4 | One whole subset file per query, from the newest or a pinned product version |
| <span id="noaagfs"></span>[GFS model output](noaa/gfs.md) | Released | GRIB2 | Global files, whole or by named GRIB2 message, chosen by run initialization window, cycle hour, forecast hours, and grid resolution |
| <span id="noaahrrr"></span>[HRRR model output](noaa/hrrr.md) | Released | GRIB2 | CONUS files, whole or by named GRIB2 message, chosen by run initialization window, cycle hour, forecast hours, and file variant |
| <span id="noaanbm"></span>[NBM forecast guidance](noaa/nbm.md) | Released | GRIB2 | Regional core files, whole or by named GRIB2 message, chosen by run initialization window, cycle hour, forecast hours, and region |
| <span id="noaarap"></span>[RAP model output](noaa/rap.md) | Released | GRIB2 | Files, whole or by named GRIB2 message, chosen by run initialization window, cycle hour, forecast hours, and file family |
| <span id="noaaclimate-normals"></span>[30-year station climate normals](noaa/climate-normals.md) | Released | CSV | Hourly, daily, monthly, or annual/seasonal normals per station; optional month-day window except annual/seasonal; hourly returns whole days |
| <span id="noaacoops-currents"></span>[Coastal current speed and direction](noaa/coops-currents.md) | Released | CSV | Native six-minute observations for one station and explicit bin; at most 28 days |
| <span id="noaacoops-water-levels"></span>[Coastal water levels](noaa/coops-water-levels.md) | Released | CSV | Six-minute observations for one station and datum; at most 28 days |
| <span id="noaacoops-tide-predictions"></span>[Coastal tide predictions](noaa/coops-tide-predictions.md) | Released | CSV | Predictions for one station and datum on a chosen interval; at most a year |
| <span id="noaacoastwatch-sst"></span>[Sea-surface temperature](noaa/coastwatch-sst.md) | Released | CSV with units row | Grid centers and timestamps inside the requested bounds; optional stride |
| <span id="usgsearthquakes"></span>[Earthquake events](usgs/earthquakes.md) | Released | CSV | Events inside an inclusive UTC window and optional box, magnitude, and depth bounds |
| <span id="usgswater-daily"></span>[Daily water observations](usgs/water-daily.md) | Released | CSV | Site observations for inclusive local calendar dates; parameter and statistic filters |
| <span id="femadisaster-declarations"></span>[Federal disaster declarations by county](fema/disaster-declarations.md) | Released | CSV | Declarations whose incident period overlaps an inclusive UTC window, for a named state or county; a county also returns its state's statewide designations |

## Browse by provider

| Provider | Released | Source only | Planned |
|---|---:|---:|---:|
| [NOAA](noaa.md) | 23 | 0 | 14 |
| [USGS](usgs.md) | 2 | 0 | 1 |
| [FEMA](fema.md) | 1 | 0 | 1 |
| [Census Bureau](census.md) | 0 | 0 | 1 |
| [EPA](epa.md) | 0 | 0 | 1 |
| [NASA](nasa.md) | 0 | 0 | 1 |
| [USDA](usda.md) | 0 | 0 | 1 |

Planned entries are listed separately on each provider page. See [versions and targets](versions.md) for future work.
