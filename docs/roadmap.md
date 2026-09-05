# Roadmap

## Why

U.S. agencies publish enormous volumes of scientific data, but every source has
its own portal, API, protocol, storage system, and format. Getting the inputs
for one analysis means learning NODD S3 layouts, NCEI query parameters, ERDDAP
URL grammar, CMR, and more, and none of it records where a file came from once
it lands on disk.

usdata is a Python SDK and CLI that hides that fragmentation behind one
interface, and records provenance for everything it fetches so a dataset can be
rebuilt from a manifest. Think "pip for U.S. scientific data": discovery,
acquisition, normalization, and provenance are the SDK's job; transformation
and publishing to Hugging Face, Zenodo, or Kaggle belong downstream.

## Phases

Each phase adds an access pattern or a piece of the reproducibility spine, not
just datasets. Which datasets land in which phase is recorded in the registry
(`target:` field) and rendered below; this section describes the rest.

**Shipped (v0.2)**: skeleton, curated registry, query normalization, CLI, cache
with checksum verification and provenance sidecars, the NCEI REST pattern
(GHCN-Daily) and the anonymous S3 pattern (NEXRAD Level II). v0.1.0 was a
name-reserving placeholder.

**Now (v0.3)**: finish the reproducibility spine and the third access pattern.

- [ ] ERDDAP protocol client with griddap subsetting
- [x] `usdata pull manifest.yaml` producing a lockfile; `usdata verify` against it
- [ ] Full state and county bounding boxes generated from Census boundary files

**Next (v0.4)**: first cross-provider phase and the bulk-file patterns.

- [ ] USGS provider; confirm legacy NWIS versus the new Water Data APIs first
- [ ] NASA provider wrapping `earthaccess`; design how credentials enter the system (ADR)
- [ ] NCEI bulk-file directory pattern (HTTPS listings, per-year archives)
- [ ] Single-file archive pattern (one download, no listing)
- [ ] Second S3 dataset reusing the NEXRAD path with product selection

**v0.5**: more APIs and gridded products.

- [ ] CO-OPS tides and currents REST pattern
- [ ] Further NCEI Access Data Service datasets sharing the GHCN client
- [ ] Gridded S3 products with product and level selection (MRMS)
- [ ] Optional `open()` on fetched assets behind extras (pandas, xarray, geopandas)

**v0.6**: model output and climate data records.

- [ ] GRIB2 model output on S3 with cycle and forecast-hour selection
- [ ] NetCDF CDRs and static global grids
- [ ] Remote cache backends (S3 and R2 compatible) behind `fsspec`

## Datasets by version

<!-- datasets:start -->
Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

Move a dataset between phases by editing its `target` in the registry.

**Target 0.3**

- [`noaa:coastwatch-sst`](providers/noaa.md#noaacoastwatch-sst) CoastWatch Blended Sea Surface Temperature · stub

**Target 0.4**

- [`nasa:gpm-imerg`](providers/nasa.md#nasagpm-imerg) GPM IMERG Precipitation · planned
- [`noaa:goes-abi`](providers/noaa.md#noaagoes-abi) GOES-R ABI Satellite Imagery · planned
- [`noaa:hurdat2`](providers/noaa.md#noaahurdat2) HURDAT2 Atlantic and Pacific Best Tracks · planned
- [`noaa:ibtracs`](providers/noaa.md#noaaibtracs) IBTrACS Global Tropical Cyclone Tracks · planned
- [`noaa:storm-events`](providers/noaa.md#noaastorm-events) Storm Events Database · planned
- [`usgs:water-daily`](providers/usgs.md#usgswater-daily) Streamflow and Water Daily Values · planned

**Target 0.5**

- [`noaa:climate-normals`](providers/noaa.md#noaaclimate-normals) U.S. Climate Normals 1991-2020 · planned
- [`noaa:coops-water-levels`](providers/noaa.md#noaacoops-water-levels) CO-OPS Water Levels and Tides · planned
- [`noaa:gsom`](providers/noaa.md#noaagsom) Global Summary of the Month · planned
- [`noaa:gsoy`](providers/noaa.md#noaagsoy) Global Summary of the Year · planned
- [`noaa:mrms`](providers/noaa.md#noaamrms) Multi-Radar Multi-Sensor (MRMS) · planned

**Target 0.6**

- [`noaa:etopo`](providers/noaa.md#noaaetopo) ETOPO 2022 Global Relief · planned
- [`noaa:gfs`](providers/noaa.md#noaagfs) GFS Forecast Model Output · planned
- [`noaa:hrrr`](providers/noaa.md#noaahrrr) HRRR Forecast Model Output · planned
- [`noaa:oisst`](providers/noaa.md#noaaoisst) OISST Daily Sea Surface Temperature · planned

**Later**

- [`census:acs-5year`](providers/census.md#censusacs-5year) American Community Survey 5-Year Estimates · planned
- [`epa:aqs-daily`](providers/epa.md#epaaqs-daily) Air Quality System Daily Summaries · planned
- [`fema:nfhl`](providers/fema.md#femanfhl) National Flood Hazard Layer · planned
- [`noaa:cdr-ndvi`](providers/noaa.md#noaacdr-ndvi) NDVI Climate Data Record · planned
- [`noaa:ersst`](providers/noaa.md#noaaersst) ERSST Monthly Sea Surface Temperature · planned
- [`noaa:ghcn-hourly`](providers/noaa.md#noaaghcn-hourly) GHCN-Hourly Station Observations · planned
- [`noaa:goes-glm`](providers/noaa.md#noaagoes-glm) GOES Geostationary Lightning Mapper · planned
- [`noaa:lcd`](providers/noaa.md#noaalcd) Local Climatological Data · planned
- [`noaa:nbm`](providers/noaa.md#noaanbm) National Blend of Models · planned
- [`noaa:nclimdiv`](providers/noaa.md#noaanclimdiv) nClimDiv Climate Divisional Data · planned
- [`noaa:nexrad-level3`](providers/noaa.md#noaanexrad-level3) NEXRAD Level III Products · planned
- [`noaa:ocads`](providers/noaa.md#noaaocads) Ocean Carbon and Acidification Data System · planned
- [`noaa:paleo-search`](providers/noaa.md#noaapaleo-search) World Data Service for Paleoclimatology · planned
- [`noaa:sea-ice-index`](providers/noaa.md#noaasea-ice-index) Sea Ice Index · planned
- [`noaa:swpc-realtime`](providers/noaa.md#noaaswpc-realtime) SWPC Real-Time Space Weather Products · planned
- [`noaa:tsunami-events`](providers/noaa.md#noaatsunami-events) Global Historical Tsunami Database · planned
- [`usda:cropland-data-layer`](providers/usda.md#usdacropland-data-layer) Cropland Data Layer · planned
- [`usgs:3dep-elevation`](providers/usgs.md#usgs3dep-elevation) 3DEP Elevation · planned
- [`usgs:earthquakes`](providers/usgs.md#usgsearthquakes) Earthquake Catalog (ComCat) · planned

**Shipped in 0.2**

- [`noaa:ghcn-daily`](providers/noaa.md#noaaghcn-daily) GHCN-Daily Station Observations · available
- [`noaa:nexrad-level2`](providers/noaa.md#noaanexrad-level2) NEXRAD Level II Radar · available
<!-- datasets:end -->

## Later

- `usdata discover`: live search over agency catalogs (NOAA OneStop, NASA CMR,
  data.gov) to find datasets worth adding to the curated registry.
- Registry entries loadable from user or third-party plugins.
- Additional providers: EPA, FEMA, Census, USDA.
- Format normalization to Parquet, GeoParquet, NetCDF, or Zarr.
- Arbitrary place-name geocoding beyond states and counties.
