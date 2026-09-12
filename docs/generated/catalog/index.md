# Find a dataset

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

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
| <span id="usgswater-daily"></span>[Daily water observations](usgs/water-daily.md) | Released | CSV | Site observations for inclusive local calendar dates; parameter and statistic filters |

## Browse by provider

| Provider | Released | Source only | Planned |
|---|---:|---:|---:|
| [NOAA](noaa.md) | 10 | 0 | 19 |
| [USGS](usgs.md) | 1 | 0 | 2 |
| [Census Bureau](census.md) | 0 | 0 | 1 |
| [EPA](epa.md) | 0 | 0 | 1 |
| [FEMA](fema.md) | 0 | 0 | 1 |
| [NASA](nasa.md) | 0 | 0 | 1 |
| [USDA](usda.md) | 0 | 0 | 1 |

Planned entries are listed separately on each provider page. See [versions and targets](versions.md) for future work.
