# usdata

[![PyPI](https://img.shields.io/pypi/v/usdata)](https://pypi.org/project/usdata/)
[![Python](https://img.shields.io/pypi/pyversions/usdata)](https://pypi.org/project/usdata/)
[![CI](https://github.com/jakeryderv/usdata/actions/workflows/ci.yml/badge.svg)](https://github.com/jakeryderv/usdata/actions/workflows/ci.yml)
[![Live checks](https://github.com/jakeryderv/usdata/actions/workflows/integration.yml/badge.svg)](https://github.com/jakeryderv/usdata/actions/workflows/integration.yml)
[![License](https://img.shields.io/github/license/jakeryderv/usdata)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-docs.usdata.dev-2f5bea)](https://docs.usdata.dev/)

[![usdata.dev: public science, reproducible inputs](https://usdata.dev/og.png)](https://usdata.dev/)

Reproducible acquisition of U.S. public scientific data. One Python SDK and
CLI discovers curated datasets from agencies such as NOAA, USGS, and EPA,
fetches their files, and keeps a record of every input: a manifest names them,
a lockfile pins them by checksum, and the record of what was fetched is what a
methods section cites. Analysis stays in pandas and xarray; usdata only
acquires. If you need every product one agency publishes, that agency's own
library is the better tool; usdata is for pinning inputs across sources and
proving later that they have not changed.

```sh
pip install "usdata[pandas]"
usdata search precipitation --location Oklahoma
usdata fetch noaa:ghcn-daily -p stations=USW00013967 --start 2024-05-06 --end 2024-05-07
```

Save the same station query as `dataset.yaml` in your working directory:

```yaml
name: first-station
sources:
  - dataset: noaa:ghcn-daily
    start: 2024-05-06
    end: 2024-05-07
    params:
      stations: USW00013967
```

Then fetch and pin its inputs, and print their citation:

```sh
usdata pull dataset.yaml && usdata cite dataset.yaml
```

The first pull writes `dataset.lock.json`; later pulls restore its pinned assets.

From Python, using the same `dataset.yaml`:

```python
from usdata import build_query, fetch, get, pull

query = build_query(start="2024-05-06", end="2024-05-07", stations="USW00013967")
items = fetch(get("noaa:ghcn-daily"), query)
frame = items[0].open()  # pandas DataFrame, units and provenance in frame.attrs
result = pull("dataset.yaml")  # every manifest source, pinned in dataset.lock.json
print(result.fetched[0].provenance.checksum)  # what usdata cite reports
```

**Alpha.** Releases are tested and lockfiles are stable, but the Python API
and CLI can change between minor versions; the [changelog](CHANGELOG.md) marks
breaking changes.

## Where to look

| | |
| --- | --- |
| [usdata.dev](https://usdata.dev/) | What it is for: the [dataset browser](https://usdata.dev/datasets/) and [worked examples](https://usdata.dev/studies/) with saved results |
| [docs.usdata.dev](https://docs.usdata.dev/) | How to use it: [install](https://docs.usdata.dev/install/), [getting started](https://docs.usdata.dev/getting-started/), guides, dataset notes, and reference |
| [Severe-weather case study](https://usdata.dev/studies/severe-weather-case-study/) | One tornado, six sources, one manifest and lockfile, ending in a citation |

Twenty-seven datasets are available today and nineteen more are planned, grouped
by agency and product family in the [catalog](docs/providers/README.md).

## How this compares

usdata resolves a place, a time window, and a few parameters to the exact
files that satisfy them, then pins those files so the same inputs can be
restored and verified later. Neighbouring tools each do part of that.

| Tool | What it does | What usdata adds |
| --- | --- | --- |
| [pooch](https://www.fatiando.org/pooch/) | Downloads and verifies files from a registry of names, hashes, and a base URL you write | Discovery: the query resolves to the URLs, and the lockfile is written, not authored |
| [intake](https://intake.readthedocs.io/) | Describes datasets in catalogs and opens them through drivers | Checksums, lockfiles, and provenance; usdata stops at handing a file to pandas or xarray |
| [DVC](https://dvc.org/) | Versions data files and can track one URL by its ETag or hash | Knowing which URLs a scientific question needs, across agencies |
| [Herbie](https://herbie.readthedocs.io/) | Deep access to model output, including subsetting GRIB2 through index files | One interface across observations, radar, satellite, and models, with a lockfile; usdata's index-file fetch reproduces Herbie's for that reason |
| [dataretrieval](https://github.com/DOI-USGS/dataretrieval-python) | Full coverage of USGS water data | Cross-agency pinning; use dataretrieval for USGS breadth |

## Contributing

Setup, commands, checks, and the release procedure are in
[CONTRIBUTING.md](CONTRIBUTING.md). The project record lives beside it:
[architecture](docs/architecture.md), [testing](docs/testing.md),
[decisions](docs/adr/README.md), [roadmap](docs/roadmap.md), and
[versioning](docs/versioning.md). The main way the project grows is a new
dataset, following [adding a dataset](docs/guides/adding-a-dataset.md).

## License

[Apache-2.0](LICENSE).
