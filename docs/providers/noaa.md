# NOAA datasets

NOAA datasets use several independent services. Choose a dataset below for its
query requirements, file format, and scientific limits. All currently supported
NOAA access is anonymous.

| Dataset | Read this guide | Download granularity |
|---|---|---|
| `ghcn-daily` | [Daily station observations](noaa-ghcn.md) | Station CSV for inclusive dates |
| `gsom` | [Monthly station summaries](noaa-gsom.md) | Complete UTC months |
| `gsom-station-files` | [GSOM station files](noaa-gsom-station-files.md) (v0.33) | One whole monthly record per station, every element |
| `gsoy` | [Annual station summaries](noaa-gsoy.md) (v0.10.0) | Complete UTC years |
| `climate-normals` | [30-year station normals](noaa-normals.md) (v0.11.0) | Whole-year or month-day windows per period |
| `lcd` | [Hourly airport observations](noaa-lcd.md) (v0.14.0) | Every report on whole days per station chunk |
| `nexrad-level2` | [Radar scans](noaa-nexrad.md) | Whole Level II scans |
| `nexrad-level3` | [Derived radar products](noaa-nexrad-level3.md) (v0.15) | Whole Level III product files, no reader |
| `mrms` | [MRMS gridded radar products](noaa-mrms.md) (v0.15.0) | Whole two-minute CONUS grids of one product, at most a day |
| `goes-abi` | [GOES imagery and cloud-top products](noaa-goes.md) | Whole scenes of one ABI product: CONUS, full-disk, or explicit M1/M2 imagery (single-channel or 16-band) and cloud-top height, temperature, pressure, and phase |
| `goes-glm` | [GOES lightning detections](noaa-glm.md) (v0.15.0) | Whole 20-second detection files, at most a day |
| `hrrr` | [HRRR model output](noaa-hrrr.md) (v0.15.0) | Whole CONUS GRIB2 files per run and forecast hour |
| `gfs` | [GFS model output](noaa-gfs.md) (v0.15.0) | Whole global GRIB2 files per run, forecast hour, and resolution |
| `rap` | [RAP model output](noaa-rap.md) (v0.20.0) | Whole 13 km GRIB2 files per run, forecast hour, and file family |
| `nbm` | [NBM forecast guidance](noaa-nbm.md) (v0.20.0) | Whole regional GRIB2 core files per hourly run and forecast hour |
| `storm-events` | [Storm Events](noaa-storm-events.md) | Whole annual archives of the details, fatalities, or locations table |
| `spc-tornado-reports` | [SPC tornado reports](noaa-spc-tornado.md) (v0.15.0) | Whole annual, half-decade, or decade files of the tornado, hail, or wind database |
| `nws-vtec-events` | [NWS watches and warnings by county](noaa-nws-vtec-events.md) | Events issued for one county or UGC inside a window, from IEM's archive |
| `nws-damage-surveys` | [NWS damage surveys](noaa-nws-damage-surveys.md) (v0.34) | GeoJSON pages of one layer's points, tracks, or areas, cut by object-id range |
| `nws-damage-photos` | [NWS damage survey photos](noaa-nws-damage-photos.md) (v0.34) | One JPEG or PNG per damage point attachment, at most 7 days |
| `emergency-response-imagery` | [NGS emergency response imagery](noaa-emergency-response-imagery.md) (v0.34) | Whole post-event GeoTIFF tiles of one event, by folder and tile footprint |
| `hurdat2` | [Tropical cyclone best tracks](noaa-hurdat2.md) (v0.12.0) | One whole basin file per revision |
| `ibtracs` | [Global tropical cyclone best tracks](noaa-ibtracs.md) (v0.20.0) | One whole subset file, CSV or NetCDF, from the newest or a pinned version |
| `coastwatch-sst` | [Sea-surface temperature](noaa-coastwatch.md) | Spatial and temporal CSV subsets |
| `ersst` | [ERSST v6 monthly sea surface temperature](noaa-ersst.md) (v0.33) | Whole global monthly NetCDF4 files |
| `enso-indices` | [CPC ENSO indices](noaa-enso-indices.md) (v0.33) | One whole index table, RONI or ONI, every season from 1950 |
| `coops-water-levels` | [Observed coastal water levels](noaa-coops.md) (v0.10.0) | One station and datum, at most 28 days |
| `coops-currents` | [Observed current speed and direction](noaa-coops-currents.md) (v0.24.0) | One station and explicit bin, at most 28 days |
| `coops-tide-predictions` | [Tide predictions](noaa-coops-predictions.md) (v0.14.0) | One station, datum, and interval, at most a year |

See the [generated catalog](../generated/catalog/noaa.md) for status,
capabilities, endpoints, and versions. Historical endpoint probes and candidate
sources are in [service research notes](noaa-services.md).

Geographic queries use bounding rectangles, which can include stations outside
a state's actual boundary. See [place lookup](../reference/places.md). Use
explicit station IDs when exact selection matters. NOAA data is generally a
U.S. Government work in the public domain; check each source's license.

## NEXRAD Level III products

See [NEXRAD Level III products](noaa-nexrad-level3.md).

## MRMS gridded radar products

See [MRMS gridded radar products](noaa-mrms.md).

## GOES ABI imagery and cloud-top products

See [GOES ABI imagery and cloud-top products](noaa-goes.md).

## GOES GLM lightning detections

See [GOES GLM lightning detections](noaa-glm.md).

## HRRR model output

See [HRRR model output](noaa-hrrr.md).

## GFS model output

See [GFS model output](noaa-gfs.md).

### RAP

See [RAP model output](noaa-rap.md).

### NBM

See [NBM forecast guidance](noaa-nbm.md).

## ERSST monthly sea surface temperature

See [ERSST v6 monthly sea surface temperature](noaa-ersst.md).

## CPC ENSO indices

See [CPC ENSO indices](noaa-enso-indices.md).

## Storm Events annual tables

See [Storm Events annual tables](noaa-storm-events.md).

## SPC tornado, hail, and wind reports

See [SPC tornado reports](noaa-spc-tornado.md).

## NWS watches and warnings by county

See [NWS watches and warnings by county](noaa-nws-vtec-events.md).

## NWS damage surveys and photos

See [NWS damage surveys](noaa-nws-damage-surveys.md) and
[NWS damage survey photos](noaa-nws-damage-photos.md).

## NGS emergency response imagery

See [NGS emergency response imagery](noaa-emergency-response-imagery.md).

## HURDAT2 best tracks

See [HURDAT2 best tracks](noaa-hurdat2.md).

## IBTrACS global best tracks

See [IBTrACS global best tracks](noaa-ibtracs.md).

## Global Summary of the Month

See [Global Summary of the Month](noaa-gsom.md).

## Global Summary of the Year

See [Global Summary of the Year](noaa-gsoy.md).

## U.S. Climate Normals

See [U.S. Climate Normals 1991-2020](noaa-normals.md).

## Local Climatological Data

See [Local Climatological Data](noaa-lcd.md).

## CoastWatch SST

See [CoastWatch SST](noaa-coastwatch.md).

## CO-OPS observed water levels

See [CO-OPS observed water levels](noaa-coops.md).

## CO-OPS tide predictions

See [CO-OPS tide predictions](noaa-coops-predictions.md).

## Access notes

See [service notes](noaa-services.md#access-notes).

## Query validation

Use the dataset guides above for supported query options.

## Data landscape

See the [research inventory](noaa-services.md#data-landscape).

## Datasets

See the [generated catalog](../generated/catalog/noaa.md).
