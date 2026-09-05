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

**Shipped (v0.3)**: manifest pull, locked restoration, and local verification.

**Shipped (v0.4)**: harden reproducibility before expanding dataset support.

- [x] Verified cache reuse and safe cache paths
- [x] Atomic file and metadata replacement with recovery from interrupted downloads
- [x] Strict manifest fields and consistent CLI input errors
- [x] Provider resource ownership and custom registry fixes
- [x] Publishing gated on successful CI for the exact release commit

**Now (v0.5)**: cross-provider access, gridded subsetting, and trustworthy inputs.

- [x] USGS daily values via the modern Water Data API (next release; available from source)
- [ ] [CoastWatch SST and ERDDAP griddap](https://github.com/jakeryderv/usdata/issues/5):
  a verified dataset, spatial/time/variable subsetting, stable asset IDs, and a tiny live test
- [ ] [State and county lookup](https://github.com/jakeryderv/usdata/issues/7):
  generated Census bounding boxes, names/postal codes/FIPS, documented vintage and limits
- [x] [Review follow-ups](https://github.com/jakeryderv/usdata/issues/30) (implemented in source):
  empty-source policy, manifest consistency, strict provider params,
  bounded HTTP retries, manifest guide, and installed-wheel CI checks

Release acceptance: all remaining items above complete, `just check` and the live
integration suite pass, and the NOAA/USGS manifest example pulls, restores, and
verifies. v0.5 does not require the entire NOAA expansion backlog.

**Following v0.5 (not yet assigned a release)**:

- [Optional `open()`](https://github.com/jakeryderv/usdata/issues/10), starting with CSV
  and NetCDF readers behind extras once the gridded adapter is established
- Further NCEI Access Data Service datasets (GSOM, GSOY, climate normals)
- Bulk directories and archives (Storm Events, HURDAT2, IBTrACS)
- A second S3 dataset with product selection (GOES ABI), then MRMS
- CO-OPS tides and currents
- Progress reporting and download-size summaries for large fetches

Refine each access pattern into an issue with acceptance criteria when it becomes
next. Registry targets remain `later` until a release commitment is made.

**v0.6**: model output and climate data records.

- [ ] NASA provider wrapping `earthaccess`; design credential handling first (ADR)
- [ ] GRIB2 model output on S3 with cycle and forecast-hour selection
- [ ] NetCDF CDRs and static global grids
- [ ] Remote cache backends (S3 and R2 compatible) behind `fsspec`

## Datasets by version

<!-- datasets:start -->
Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

Move a dataset between phases by editing its `target` in the registry.

**Target 0.5**

- [`noaa:coastwatch-sst`](providers/noaa.md#noaacoastwatch-sst) CoastWatch Blended Sea Surface Temperature · stub

**Target 0.6**

- [`nasa:gpm-imerg`](providers/nasa.md#nasagpm-imerg) GPM IMERG Precipitation · planned
- [`noaa:etopo`](providers/noaa.md#noaaetopo) ETOPO 2022 Global Relief · planned
- [`noaa:gfs`](providers/noaa.md#noaagfs) GFS Forecast Model Output · planned
- [`noaa:hrrr`](providers/noaa.md#noaahrrr) HRRR Forecast Model Output · planned
- [`noaa:oisst`](providers/noaa.md#noaaoisst) OISST Daily Sea Surface Temperature · planned

**Later**

- [`census:acs-5year`](providers/census.md#censusacs-5year) American Community Survey 5-Year Estimates · planned
- [`epa:aqs-daily`](providers/epa.md#epaaqs-daily) Air Quality System Daily Summaries · planned
- [`fema:nfhl`](providers/fema.md#femanfhl) National Flood Hazard Layer · planned
- [`noaa:cdr-ndvi`](providers/noaa.md#noaacdr-ndvi) NDVI Climate Data Record · planned
- [`noaa:climate-normals`](providers/noaa.md#noaaclimate-normals) U.S. Climate Normals 1991-2020 · planned
- [`noaa:coops-water-levels`](providers/noaa.md#noaacoops-water-levels) CO-OPS Water Levels and Tides · planned
- [`noaa:ersst`](providers/noaa.md#noaaersst) ERSST Monthly Sea Surface Temperature · planned
- [`noaa:ghcn-hourly`](providers/noaa.md#noaaghcn-hourly) GHCN-Hourly Station Observations · planned
- [`noaa:goes-abi`](providers/noaa.md#noaagoes-abi) GOES-R ABI Satellite Imagery · planned
- [`noaa:goes-glm`](providers/noaa.md#noaagoes-glm) GOES Geostationary Lightning Mapper · planned
- [`noaa:gsom`](providers/noaa.md#noaagsom) Global Summary of the Month · planned
- [`noaa:gsoy`](providers/noaa.md#noaagsoy) Global Summary of the Year · planned
- [`noaa:hurdat2`](providers/noaa.md#noaahurdat2) HURDAT2 Atlantic and Pacific Best Tracks · planned
- [`noaa:ibtracs`](providers/noaa.md#noaaibtracs) IBTrACS Global Tropical Cyclone Tracks · planned
- [`noaa:lcd`](providers/noaa.md#noaalcd) Local Climatological Data · planned
- [`noaa:mrms`](providers/noaa.md#noaamrms) Multi-Radar Multi-Sensor (MRMS) · planned
- [`noaa:nbm`](providers/noaa.md#noaanbm) National Blend of Models · planned
- [`noaa:nclimdiv`](providers/noaa.md#noaanclimdiv) nClimDiv Climate Divisional Data · planned
- [`noaa:nexrad-level3`](providers/noaa.md#noaanexrad-level3) NEXRAD Level III Products · planned
- [`noaa:ocads`](providers/noaa.md#noaaocads) Ocean Carbon and Acidification Data System · planned
- [`noaa:paleo-search`](providers/noaa.md#noaapaleo-search) World Data Service for Paleoclimatology · planned
- [`noaa:sea-ice-index`](providers/noaa.md#noaasea-ice-index) Sea Ice Index · planned
- [`noaa:storm-events`](providers/noaa.md#noaastorm-events) Storm Events Database · planned
- [`noaa:swpc-realtime`](providers/noaa.md#noaaswpc-realtime) SWPC Real-Time Space Weather Products · planned
- [`noaa:tsunami-events`](providers/noaa.md#noaatsunami-events) Global Historical Tsunami Database · planned
- [`usda:cropland-data-layer`](providers/usda.md#usdacropland-data-layer) Cropland Data Layer · planned
- [`usgs:3dep-elevation`](providers/usgs.md#usgs3dep-elevation) 3DEP Elevation · planned
- [`usgs:earthquakes`](providers/usgs.md#usgsearthquakes) Earthquake Catalog (ComCat) · planned

**Implemented, unreleased (planned 0.5)**

- [`usgs:water-daily`](providers/usgs.md#usgswater-daily) Streamflow and Water Daily Values · available

**Included since 0.2**

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
