# USGS datasets

<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

[Provider access notes](../../providers/usgs.md).

**Released** is included in usdata 0.26.0. **Source only** is implemented in this checkout and requires a source installation. **Planned** cannot fetch data yet.

## Implemented datasets

| Dataset | Availability | Files | What gets selected |
|---|---|---|---|
| <span id="usgsearthquakes"></span>[Earthquake events](../../providers/usgs-earthquakes.md) | Released | CSV | Events inside an inclusive UTC window and optional box, magnitude, and depth bounds |
| <span id="usgswater-daily"></span>[Daily water observations](../../providers/usgs-water-daily.md) | Released | CSV | Site observations for inclusive local calendar dates; parameter and statistic filters |

## Planned datasets

These entries are not implemented; they cannot fetch data.

### usgs:3dep-elevation

**3DEP Elevation** · Planned · target later

Seamless digital elevation models from the 3D Elevation Program (1/3 arc-second and 1 m where available). Tiled rasters on public cloud storage; spatial selection by tile.

[Upstream information](https://www.usgs.gov/3d-elevation-program)
Domain: Terrain and elevation.
