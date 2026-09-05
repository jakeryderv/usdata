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

## Shipped (v0.2)

v0.1.0 on PyPI was a name-reserving placeholder. v0.2.0 proves the
abstraction against two NOAA datasets with different access patterns.

- Skeleton: models, curated registry, query normalization, CLI, tests, CI
- `noaa:ghcn-daily` adapter (NCEI search service for stations, data service for CSV)
- `noaa:nexrad-level2` adapter (unidata-nexrad-level2 S3, anonymous listing, site lookup)
- Cache with checksum verification, provenance sidecars written on fetch

## Now (v0.3)

Finish the reproducibility spine and the third access pattern.

- [ ] `noaa:coastwatch-sst` adapter (ERDDAP, true server-side subsetting)
- [ ] `usdata pull manifest.yaml` producing a lockfile; `usdata verify` against it
- [ ] Full state and county bounding boxes generated from Census boundary files

## Next (v0.4)

- USGS provider. Verify the current status of legacy NWIS services versus the
  new Water Data APIs before choosing an endpoint.
- NASA provider wrapping `earthaccess` (CMR search plus Earthdata Login).
- Optional `open()` on fetched assets dispatching to xarray, pandas, or
  geopandas behind extras. Core stays dependency-light.
- Remote cache backends (S3 and R2 compatible) behind `fsspec`.

## Later

- `usdata discover`: live search over agency catalogs (NOAA OneStop, NASA CMR,
  data.gov) to find datasets worth adding to the curated registry.
- Registry entries loadable from user or third-party plugins.
- Additional providers: EPA, FEMA, Census, USDA.
- Format normalization to Parquet, GeoParquet, NetCDF, or Zarr.
- Arbitrary place-name geocoding beyond states and counties.
