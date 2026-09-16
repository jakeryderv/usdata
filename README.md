# usdata

[![PyPI](https://img.shields.io/pypi/v/usdata)](https://pypi.org/project/usdata/)
[![Python](https://img.shields.io/pypi/pyversions/usdata)](https://pypi.org/project/usdata/)
[![CI](https://github.com/jakeryderv/usdata/actions/workflows/ci.yml/badge.svg)](https://github.com/jakeryderv/usdata/actions/workflows/ci.yml)
[![Live checks](https://github.com/jakeryderv/usdata/actions/workflows/integration.yml/badge.svg)](https://github.com/jakeryderv/usdata/actions/workflows/integration.yml)
[![License](https://img.shields.io/github/license/jakeryderv/usdata)](LICENSE)

Reproducible acquisition of U.S. public scientific data. One Python SDK and
CLI discovers curated NOAA and USGS datasets, fetches their files, and keeps a
record of every input: a manifest names them, a lockfile pins them by checksum,
and the record of what was fetched is what a methods section cites. Analysis
stays in pandas and xarray; usdata only acquires.

```sh
pip install "usdata[pandas]"
usdata search precipitation --location Oklahoma
usdata fetch noaa:ghcn-daily -p stations=USW00013967 --start 2024-05-06 --end 2024-05-07
usdata pull dataset.yaml && usdata cite dataset.yaml
```

**Alpha.** Releases are tested and lockfiles are stable, but the Python API
and CLI can change between minor versions; the [changelog](CHANGELOG.md) marks
breaking changes.

## Where to look

| | |
| --- | --- |
| [usdata.dev](https://usdata.dev/) | What it is for: the [dataset browser](https://usdata.dev/datasets/) and [worked examples](https://usdata.dev/examples/) with saved results |
| [docs.usdata.dev](https://docs.usdata.dev/) | How to use it: [install](https://docs.usdata.dev/install/), [getting started](https://docs.usdata.dev/getting-started/), guides, dataset notes, and reference |
| [Severe-weather case study](https://usdata.dev/examples/severe-weather-case-study/) | One tornado, six sources, one manifest and lockfile, ending in a citation |

Twenty datasets are available today and twenty-five more are planned, grouped
by agency and product family in the [catalog](docs/providers/README.md).

## Contributing

Setup, commands, checks, and the release procedure are in
[CONTRIBUTING.md](CONTRIBUTING.md). The project record lives beside it:
[architecture](docs/architecture.md), [testing](docs/testing.md),
[decisions](docs/adr/README.md), [roadmap](docs/roadmap.md), and
[versioning](docs/versioning.md). The main way the project grows is a new
dataset, following [adding a dataset](docs/guides/adding-a-dataset.md).

## License

[Apache-2.0](LICENSE).
