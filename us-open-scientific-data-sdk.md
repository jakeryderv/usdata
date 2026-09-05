# U.S. Open Scientific Data SDK

## Project Idea

A unified **Python SDK + CLI** for discovering, accessing, subsetting, downloading, and tracking provenance for U.S. public scientific data.

The goal is to hide the complexity of government data portals, APIs, protocols, storage systems, and formats behind a consistent interface.

> **Concept:** "pip for U.S. scientific data."

## Example Data Providers

- **NOAA** — weather, climate, radar, satellite, ocean, fisheries
- **NASA** — Earth observation, atmosphere, climate, space
- **USGS** — geology, earthquakes, water, terrain, land cover
- **EPA** — air, water, pollution, environmental monitoring
- **FEMA** — hazards, disasters, flood data
- **Census Bureau** — population, demographics, geography
- **USDA** — agriculture, soils, crops, forestry

## Core Interface

Users should not need to know whether data comes from ERDDAP, THREDDS, OPeNDAP, S3, an agency REST API, or a bulk-download server.

### Python

```python
from usdata import search

results = search(
    "radar",
    location="Oklahoma",
    start="2024-05-06",
    end="2024-05-07",
)

data = results[0].fetch()
```

### CLI

```bash
usdata search "tornado radar" --state OK --date 2024-05-06

usdata fetch noaa:nexrad-level2 \
    --lat 35.47 --lon -97.52 \
    --start 2024-05-06T20:00 \
    --end 2024-05-06T23:00
```

## Architecture

Use a modular, provider/plugin-based architecture.

```text
usdata/
├── core/
│   ├── catalog
│   ├── search
│   ├── query
│   ├── download
│   └── provenance
│
├── providers/
│   ├── noaa/
│   ├── nasa/
│   ├── usgs/
│   ├── epa/
│   ├── fema/
│   ├── census/
│   └── usda/
│
├── protocols/
│   ├── http
│   ├── s3
│   ├── erddap
│   ├── opendap
│   └── thredds
│
└── cli/
```

Each provider translates a common query into the agency-specific access mechanism:

```text
Unified Query
     ↓
Provider Adapter
     ↓
Agency APIs / Storage / Protocols
     ↓
Normalized Result
```

## Core Features

- **Unified discovery** — search datasets across multiple agencies.
- **Spatial and temporal queries** — standardize bounding boxes, coordinates, dates, and time ranges.
- **Smart retrieval** — automatically select APIs, cloud objects, bulk downloads, ERDDAP, etc.
- **Subsetting** — retrieve only the region, time period, or variables needed.
- **Format normalization** — optionally convert to formats such as Parquet, GeoParquet, NetCDF, or Zarr.
- **Caching** — local caching with optional S3/R2-compatible storage.
- **Provenance** — retain source agency, source object/URL, retrieval time, checksum, transformations, and licensing.
- **Reproducibility** — manifests/lockfiles can describe exactly which source data produced a derived dataset.

## Dataset Manifests

A declarative manifest could describe all inputs needed for a project:

```yaml
dataset: tornado-environment
version: 1.0

sources:
  - provider: noaa
    dataset: nexrad-level2
    date: 2024-05-06
    region: oklahoma

  - provider: usgs
    dataset: structures
    region: oklahoma

  - provider: census
    dataset: population
    year: 2020
```

Then reproduce the inputs with:

```bash
usdata pull dataset.yaml
```

## CLI Vision

```bash
usdata search ...
usdata info ...
usdata fetch ...
usdata subset ...
usdata pull ...
usdata verify ...
```

## MVP

Start with a small number of high-value providers rather than attempting every federal agency immediately.

### v0.1

1. **NOAA**
   - OneStop
   - NCEI
   - NOAA Open Data Dissemination (NODD)
   - ERDDAP
2. **USGS**
3. **NASA**

Focus first on designing a strong common dataset/query/provenance abstraction. Additional agencies can then be added primarily through new provider plugins.

## Longer-Term Vision

Create a common open-source data-access layer for U.S. scientific and public datasets:

```text
Government Data Sources
        ↓
      usdata
        ↓
Discovery → Query → Subset → Download
        ↓
Cache / R2 / S3 / Local Storage
        ↓
Reproducible Dataset Pipelines
        ↓
Hugging Face / Zenodo / Kaggle / Applications / ML
```

The SDK serves as the **discovery, acquisition, normalization, and provenance layer**, while downstream repositories define transformations and publish reproducible datasets.
