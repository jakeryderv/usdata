# USGS datasets

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

[Provider access notes](../../providers/usgs.md).

**Released** is included in usdata 0.14.0. **Source only** is implemented in this checkout and requires a source installation. **Planned** cannot fetch data yet.

## Implemented datasets

| Dataset | Availability | Files | What gets selected |
|---|---|---|---|
| <span id="usgswater-daily"></span>[Daily water observations](usgs/water-daily.md) | Released | CSV | Site observations for inclusive local calendar dates; parameter and statistic filters |

## Planned datasets

These entries are not implemented; they cannot fetch data.

### usgs:earthquakes

**Earthquake Catalog (ComCat)** · Planned · target later

Global earthquake events with location, magnitude, and depth from the ANSS Comprehensive Catalog via the FDSN event web service. Anonymous REST with bbox, time, and magnitude filters.

[Upstream information](https://earthquake.usgs.gov/fdsnws/event/1/)
Domain: Natural hazards.

### usgs:3dep-elevation

**3DEP Elevation** · Planned · target later

Seamless digital elevation models from the 3D Elevation Program (1/3 arc-second and 1 m where available). Tiled rasters on public cloud storage; spatial selection by tile.

[Upstream information](https://www.usgs.gov/3d-elevation-program)
Domain: Terrain and elevation.
