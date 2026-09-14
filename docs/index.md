# usdata

One Python SDK and CLI for U.S. scientific data. Find a dataset, fetch its
files unchanged, open them locally, and keep a record that lets anyone repeat
the download and check the bytes. Supported sources today are NOAA and USGS.

## Four commands

Search a curated catalog. Nothing is downloaded yet.

```console
$ usdata search precipitation --location Oklahoma
noaa:ghcn-daily       available  since 0.2     GHCN-Daily Station Observations
noaa:climate-normals  available  since 0.11    U.S. Climate Normals 1991-2020
noaa:gsom             available  since 0.7     Global Summary of the Month
noaa:lcd              available  since 0.14    Local Climatological Data
noaa:nexrad-level2    available  since 0.2     NEXRAD Level II Radar
noaa:mrms             available  since 0.15    Multi-Radar Multi-Sensor (MRMS)
```

Fetch two days of one station's precipitation and maximum temperature. The
file lands in a local cache with a provenance sidecar recording the source
URL, retrieval time, and checksum.

```console
$ usdata fetch noaa:ghcn-daily -p stations=USW00013967 --start 2024-05-06 --end 2024-05-07 --vars PRCP,TMAX
~/.cache/usdata/noaa/ghcn-daily/daily-summaries_2024-05-06_2024-05-07_e700cb60a834.csv	fetched	209 bytes
```

Open it. The same query in Python returns the cached file, and the pandas
extra reads it.

```python
from usdata import build_query, get
from usdata.fetch import fetch

query = build_query(
    start="2024-05-06", end="2024-05-07", variables=["PRCP", "TMAX"], stations="USW00013967"
)
items = fetch(get("noaa:ghcn-daily"), query)
print(items[0].open())
```

```text
       STATION  LATITUDE  LONGITUDE  ELEVATION        DATE  PRCP  TMAX
0  USW00013967  35.38843  -97.60035      389.9  2024-05-06  10.9  27.2
1  USW00013967  35.38843  -97.60035      389.9  2024-05-07   0.0  26.7
```

Pin it. A manifest names the query; the first pull writes a lockfile with the
checksum; verify compares local bytes against it without touching the network.

```console
$ usdata pull dataset.yaml
1 asset(s); wrote dataset.lock.json
$ usdata verify dataset.yaml
all assets match dataset.lock.json
```

## How the pieces fit

- **The registry** is a curated list of datasets with true endpoints and
  capabilities. Search reads it locally; it never queries an agency catalog.
- **An adapter** per dataset turns your query into the upstream service's own
  requests and returns whole files, never rewritten.
- **The cache** keeps those files with a provenance sidecar each. Adapters
  cannot write to it; the core does.
- **Readers** are optional extras that open a cached file into pandas or
  xarray. Without one, you still have the file and its provenance.
- **Manifests and lockfiles** make a query and its exact bytes repeatable, and
  tell you when an agency revises a file underneath you.

## Where to go

| You want to | Read |
| --- | --- |
| Do the walkthrough above yourself, including restoring into a fresh cache | [Getting started](getting-started.md) |
| Install with the right extras, or from source | [Install](install.md) |
| Learn the query options and CLI workflows | [Fetch and analyze](guides/fetch-and-analyze.md) |
| See a whole analysis with saved outputs | [Examples](https://usdata.dev/examples/) |
| Choose a dataset and learn its quirks | [Catalog](generated/catalog/index.md) and [provider notes](providers/README.md) |
| Repeat an analysis with pinned inputs | [Manifests and lockfiles](reference/manifests.md) |
| Find an exact Python argument | [Python API](reference/api.md) |

These pages describe the current source checkout. Anything marked
**Unreleased** is not yet on PyPI; see [Install](install.md#source-installation).
