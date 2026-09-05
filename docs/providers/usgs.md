# USGS

Provider id `usgs`. Homepage: https://www.usgs.gov/

## Access notes

`usgs:water-daily` uses the [modern Water Data OGC API](https://api.waterdata.usgs.gov/docs/ogcapi/),
at `https://api.waterdata.usgs.gov/ogcapi/v0/collections/daily/items`.
The [legacy WaterServices homepage](https://waterservices.usgs.gov/) announces
decommissioning in early 2027 (checked 2026-09-05), so new access targets the
modern API.

- Select sites with `-p sites=07164500` or `USGS-07164500`; comma-separated IDs
  and SDK lists are supported. A location, bbox, or point can select sites
  geographically instead. When both site IDs and a bbox are provided, both apply.
- `--vars 00060` selects streamflow. Variables are five-digit parameter codes;
  quote codes in YAML to preserve leading zeros. Omitting variables requests
  all available parameters for the selected sites and dates.
- `-p statistic_id=00003` selects daily means (the default). Other five-digit
  statistic codes can select minima or maxima. Start and end are inclusive
  local calendar dates; times of day are ignored for daily values.
- JSON pages resolve the query; each asset downloads the corresponding raw CSV.
  CSV retains coordinates, units, approval status, qualifiers, and modification
  timestamps, while excluding the volatile GeoJSON response `timeStamp`.
- Live checks on 2026-09-05 found that `sortby` is rejected beyond the first
  page. Cursor links can also fall back to `offset=1` at the end, repeating a
  record. The adapter therefore uses absolute offsets advanced by the number
  of returned observations, retaining all original filters. Requests use
  10,000 rows per page; the integration test forces one row per page.
- Access was verified without credentials. [API keys](https://api.waterdata.usgs.gov/docs/ogcapi/keys/)
  raise rate limits but are not required for the supported small queries.
  API key configuration is not exposed by this adapter.
- The [service homepage](https://api.waterdata.usgs.gov/ogcapi/v0/?f=html)
  identifies its data as US Government work in the public domain.

Reproducibility pins the CSV bytes. If observations or page membership change
upstream, restoration detects a checksum mismatch; the service does not offer
immutable versions through these requests.

Small probe used to verify the endpoint and filtering:

```sh
curl --get 'https://api.waterdata.usgs.gov/ogcapi/v0/collections/daily/items' \
  --data-urlencode 'f=csv' --data-urlencode 'monitoring_location_id=USGS-07164500' \
  --data-urlencode 'parameter_code=00060' --data-urlencode 'statistic_id=00003' \
  --data-urlencode 'time=2024-05-06/2024-05-07' --data-urlencode 'limit=1' \
  --data-urlencode 'offset=0'
```

## Datasets

<!-- datasets:start -->
Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

| Dataset | Domain | Status | Version | Description | Protocol |
|---|---|---|---|---|---|
| [`usgs:earthquakes`](#usgsearthquakes) | Natural hazards | planned | target later | Global earthquake events with location, magnitude, and depth from the ANSS Comprehensive Catalog via the FDSN event web service. | http |
| [`usgs:water-daily`](#usgswater-daily) | Water resources | available | unreleased; planned 0.5 | Daily statistics (streamflow, gage height, temperature) for USGS monitoring sites via the modern USGS Water Data OGC API. | http |
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

**Streamflow and Water Daily Values** · available · unreleased; planned 0.5

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
<!-- datasets:end -->
