# Dataset reference

<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

Each dataset has one page here: how to select it, what arrives, what the service does not say, and its generated reference. To browse datasets with previews and walkthroughs, use the [dataset grid on usdata.dev](https://usdata.dev/datasets/).

**Released** is included in usdata 0.33.0. **Source only** is implemented in this checkout and requires a source installation. **Planned** cannot fetch data yet.

## Implemented datasets

| Dataset | Availability | Files | What gets selected |
|---|---|---|---|
| <span id="noaaghcn-daily"></span>[Daily station weather](../../providers/noaa-ghcn.md) | Released | CSV | Station observations within inclusive calendar dates; selected elements |
| <span id="noaagsom"></span>[Monthly station climate](../../providers/noaa-gsom.md) | Released | CSV | Complete UTC calendar months touched by the query; station and element filters |
| <span id="noaagsoy"></span>[Annual station climate](../../providers/noaa-gsoy.md) | Released | CSV | Complete UTC calendar years touched by the query; station and element filters |
| <span id="noaalcd"></span>[Hourly airport observations](../../providers/noaa-lcd.md) | Released | CSV | Every report on whole calendar days per station; optional column filters |
| <span id="noaagsom-station-files"></span>[Whole monthly station records, one file per station](../../providers/noaa-gsom-station-files.md) | Released | CSV | One whole file per named station, every month and element it holds |
| <span id="noaastorm-events"></span>[Storm Events details, fatalities, and locations](../../providers/noaa-storm-events.md) | Released | gzip CSV | Whole annual archives of one table; filter rows locally after downloading |
| <span id="noaaspc-tornado-reports"></span>[SPC tornado, hail, and wind databases](../../providers/noaa-spc-tornado.md) | Released | CSV | Whole annual, half-decade, or decade files of one table; filter rows locally after downloading |
| <span id="noaanws-vtec-events"></span>[NWS warnings and watches by county](../../providers/noaa-nws-vtec-events.md) | Released | CSV | Events issued for one county or UGC inside an inclusive UTC window; optionally one event type |
| <span id="noaanws-damage-photos"></span>[Photos from NWS damage surveys, one file per damage point attachment](../../providers/noaa-nws-damage-photos.md) | Source only | JPEG, PNG | Each JPEG or PNG attached to a damage point with storm time in an inclusive UTC window of at most 7 days |
| <span id="noaanws-damage-surveys"></span>[NWS damage survey points, tornado tracks, and damage areas](../../providers/noaa-nws-damage-surveys.md) | Source only | GeoJSON | One layer's features with storm time in an inclusive UTC window, optionally in a box; one page per object-id run |
| <span id="noaanexrad-level2"></span>[NEXRAD radar scans](../../providers/noaa-nexrad.md) | Released | NEXRAD Level II | Whole radar scans by site and inclusive UTC scan-start time |
| <span id="noaamrms"></span>[MRMS gridded radar products](../../providers/noaa-mrms.md) | Released | GRIB2 (gzipped) | Whole two-minute CONUS grids of one product by inclusive UTC file stamp, at most one day |
| <span id="noaanexrad-level3"></span>[NEXRAD derived radar products](../../providers/noaa-nexrad-level3.md) | Released | NEXRAD Level III (no reader) | Whole product files by site, product code, and inclusive UTC scan time since 2020-03-30 |
| <span id="noaagoes-abi"></span>[GOES ABI imagery, multiband scenes, and cloud-top products](../../providers/noaa-goes.md) | Released | NetCDF4 | Whole scenes of one ABI product by inclusive UTC scan-start time, with one channel or mesoscale sector where the product has them |
| <span id="noaagoes-glm"></span>[GOES lightning detections](../../providers/noaa-glm.md) | Released | NetCDF4 | Whole 20-second detection files by inclusive UTC file-start time, at most one day |
| <span id="noaahurdat2"></span>[Tropical cyclone best tracks](../../providers/noaa-hurdat2.md) | Released | HURDAT2 fixed-format text | The newest or a named revision of one whole basin file; filter track points locally |
| <span id="noaaibtracs"></span>[Global tropical cyclone best tracks](../../providers/noaa-ibtracs.md) | Released | CSV with a units row, NetCDF4 | One whole subset file per query, from the newest or a pinned product version |
| <span id="noaagfs"></span>[GFS model output](../../providers/noaa-gfs.md) | Released | GRIB2 | Global files, whole or by named GRIB2 message, chosen by run initialization window, cycle hour, forecast hours, and grid resolution |
| <span id="noaahrrr"></span>[HRRR model output](../../providers/noaa-hrrr.md) | Released | GRIB2 | CONUS files, whole or by named GRIB2 message, chosen by run initialization window, cycle hour, forecast hours, and file variant |
| <span id="noaanbm"></span>[NBM forecast guidance](../../providers/noaa-nbm.md) | Released | GRIB2 | Regional core files, whole or by named GRIB2 message, chosen by run initialization window, cycle hour, forecast hours, and region |
| <span id="noaarap"></span>[RAP model output](../../providers/noaa-rap.md) | Released | GRIB2 | Files, whole or by named GRIB2 message, chosen by run initialization window, cycle hour, forecast hours, and file family |
| <span id="noaaclimate-normals"></span>[30-year station climate normals](../../providers/noaa-normals.md) | Released | CSV | Hourly, daily, monthly, or annual/seasonal normals per station; optional month-day window except annual/seasonal; hourly returns whole days |
| <span id="noaaenso-indices"></span>[Seasonal El Niño indices, the official RONI and the traditional ONI](../../providers/noaa-enso-indices.md) | Released | whitespace-delimited text (no reader) | One whole index table, every season from DJF 1950; select seasons locally |
| <span id="noaacoops-currents"></span>[Coastal current speed and direction](../../providers/noaa-coops-currents.md) | Released | CSV | Native six-minute observations for one station and explicit bin; at most 28 days |
| <span id="noaaersst"></span>[Monthly global 2 degree sea surface temperature since 1850](../../providers/noaa-ersst.md) | Released | NetCDF4 | Whole global monthly files, one for every month the window touches |
| <span id="noaacoops-water-levels"></span>[Coastal water levels](../../providers/noaa-coops.md) | Released | CSV | Six-minute observations for one station and datum; at most 28 days |
| <span id="noaacoops-tide-predictions"></span>[Coastal tide predictions](../../providers/noaa-coops-predictions.md) | Released | CSV | Predictions for one station and datum on a chosen interval; at most a year |
| <span id="noaacoastwatch-sst"></span>[Sea-surface temperature](../../providers/noaa-coastwatch.md) | Released | CSV with units row | Grid centers and timestamps inside the requested bounds; optional stride |
| <span id="noaaemergency-response-imagery"></span>[Post-event aerial imagery tiles](../../providers/noaa-emergency-response-imagery.md) | Source only | GeoTIFF | Whole GeoTIFFs of one event folder, optionally by subfolder and by the footprint that tile names give |
| <span id="usgsearthquakes"></span>[Earthquake events](../../providers/usgs-earthquakes.md) | Released | CSV | Events inside an inclusive UTC window and optional box, magnitude, and depth bounds |
| <span id="usgswater-daily"></span>[Daily water observations](../../providers/usgs-water-daily.md) | Released | CSV | Site observations for inclusive local calendar dates; parameter and statistic filters |
| <span id="censusacs-5year"></span>[Five-year population, housing, and income estimates by state or county](../../providers/census-acs-5year.md) | Released | JSON | One vintage's estimates for up to fifty variables over a state, its counties, or one county |
| <span id="epaaqs-daily"></span>[Daily air pollutant summaries from regulatory monitors](../../providers/epa-aqs-daily.md) | Released | JSON | Local days within inclusive UTC calendar dates for one to five pollutants; one file per year |
| <span id="femadisaster-declarations"></span>[Federal disaster declarations by county](../../providers/fema-disaster-declarations.md) | Released | CSV | Declarations whose incident period overlaps an inclusive UTC window, for a named state or county; a county also returns its state's statewide designations |

## Browse by provider

| Provider | Released | Source only | Planned |
|---|---:|---:|---:|
| [NOAA](noaa.md) | 26 | 3 | 13 |
| [USGS](usgs.md) | 2 | 0 | 1 |
| [Census Bureau](census.md) | 1 | 0 | 0 |
| [EPA](epa.md) | 1 | 0 | 0 |
| [FEMA](fema.md) | 1 | 0 | 1 |
| [NASA](nasa.md) | 0 | 0 | 1 |
| [USDA](usda.md) | 0 | 0 | 1 |

Planned entries are listed separately on each provider page. See [versions and targets](versions.md) for future work.
