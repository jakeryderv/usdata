# USGS

Provider id `usgs`. Homepage: https://www.usgs.gov/

## Access notes

No notes yet. Add how this agency publishes data, authentication requirements, quirks, and links to its own documentation as adapters get built.

## Datasets

<!-- datasets:start -->
Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

| Dataset | Status | Description | Protocol | Server-side subsetting |
|---|---|---|---|---|
| [`usgs:3dep-elevation`](#usgs3dep-elevation) | planned | Seamless digital elevation models from the 3D Elevation Program (1/3 arc-second and 1 m where available). | s3 | spatial |
| [`usgs:earthquakes`](#usgsearthquakes) | planned | Global earthquake events with location, magnitude, and depth from the ANSS Comprehensive Catalog via the FDSN event web service. | http | spatial, temporal |
| [`usgs:water-daily`](#usgswater-daily) | planned | Daily statistics (streamflow, gage height, temperature) for USGS monitoring sites. | http | spatial, temporal, variable |

### usgs:3dep-elevation

**3DEP Elevation** · planned

Seamless digital elevation models from the 3D Elevation Program (1/3 arc-second and 1 m where available). Tiled rasters on public cloud storage; spatial selection by tile.

- Homepage: https://www.usgs.gov/3d-elevation-program
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: elevation, dem, terrain, lidar, 3dep, topography
- Adapter: none yet

### usgs:earthquakes

**Earthquake Catalog (ComCat)** · planned

Global earthquake events with location, magnitude, and depth from the ANSS Comprehensive Catalog via the FDSN event web service. Anonymous REST with bbox, time, and magnitude filters.

- Homepage: https://earthquake.usgs.gov/fdsnws/event/1/
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: earthquakes, seismic, geology, hazards, comcat, fdsn
- Adapter: none yet

### usgs:water-daily

**Streamflow and Water Daily Values** · planned

Daily statistics (streamflow, gage height, temperature) for USGS monitoring sites. The legacy NWIS web services are being replaced by the USGS Water Data APIs; the adapter must target whichever is current.

- Homepage: https://api.waterdata.usgs.gov/
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: water, streamflow, discharge, rivers, gages, hydrology, nwis
- Adapter: none yet
<!-- datasets:end -->
