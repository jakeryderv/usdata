# USGS dataset catalog

[Provider access notes](../../providers/usgs.md). Status describes this source checkout; see version labels for release support.

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

| Dataset | Domain | Status | Version | Description | Protocol |
|---|---|---|---|---|---|
| [`usgs:earthquakes`](#usgsearthquakes) | Natural hazards | planned | target later | Global earthquake events with location, magnitude, and depth from the ANSS Comprehensive Catalog via the FDSN event web service. | http |
| [`usgs:water-daily`](#usgswater-daily) | Water resources | available | since 0.5 | Daily statistics (streamflow, gage height, temperature) for USGS monitoring sites via the modern USGS Water Data OGC API. | http |
| [`usgs:3dep-elevation`](#usgs3dep-elevation) | Terrain and elevation | planned | target later | Seamless digital elevation models from the 3D Elevation Program (1/3 arc-second and 1 m where available). | s3 |

### usgs:earthquakes

**Earthquake Catalog (ComCat)** · planned · target later

Global earthquake events with location, magnitude, and depth from the ANSS Comprehensive Catalog via the FDSN event web service. Anonymous REST with bbox, time, and magnitude filters.

- Domain: Natural hazards
- Server-side subsetting: spatial, temporal
- Homepage: https://earthquake.usgs.gov/fdsnws/event/1/
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: earthquakes, seismic, geology, hazards, comcat, fdsn
- Adapter: none yet

### usgs:water-daily

[Dataset and usage guide](usgs/water-daily.md).

**Streamflow and Water Daily Values** · available · since 0.5

Daily statistics (streamflow, gage height, temperature) for USGS monitoring sites via the modern USGS Water Data OGC API. Anonymous, paginated CSV downloads filtered by site or bbox, dates, and parameter codes; daily mean by default, with units and quality metadata preserved.

- Domain: Water resources
- Server-side subsetting: spatial, temporal, variable
- Homepage: https://api.waterdata.usgs.gov/
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: water, streamflow, discharge, rivers, gages, hydrology, nwis
- Adapter: `usdata.providers.usgs.daily:WaterDaily`

### usgs:3dep-elevation

**3DEP Elevation** · planned · target later

Seamless digital elevation models from the 3D Elevation Program (1/3 arc-second and 1 m where available). Tiled rasters on public cloud storage; spatial selection by tile.

- Domain: Terrain and elevation
- Server-side subsetting: spatial
- Homepage: https://www.usgs.gov/3d-elevation-program
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: elevation, dem, terrain, lidar, 3dep, topography
- Adapter: none yet
