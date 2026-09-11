# usdata

Discover U.S. scientific datasets, fetch their files, and keep a reproducible
record of where every input came from. Use the same Python SDK or CLI across
supported NOAA and USGS datasets.

**Pre-alpha.** These docs describe the current source checkout. Features marked
**Unreleased** require a source installation; consult the
[changelog](CHANGELOG.md) for published versions. Other providers are planned.

Project home: [usdata.dev](https://usdata.dev/).
[Documentation and getting started](https://docs.usdata.dev/).

## Start here

```sh
pip install usdata
usdata search precipitation --location Oklahoma
usdata info noaa:ghcn-daily
```

Search uses a curated registry. Fetching contacts the upstream service; readers
open the resulting local files. Provenance and manifests connect those steps.

- [Quick start and documentation](docs/content/index.md)
- [Fetch and analyze data](docs/content/guides/fetch-and-analyze.md)
- [Runnable examples with saved outputs](examples/README.md)
- [Readers](docs/content/reference/readers.md) and [reproducible manifests](docs/content/reference/manifests.md)

## Source installation

For features marked **Unreleased**, install this checkout with
[uv](https://docs.astral.sh/uv/):

```sh
git clone https://github.com/jakeryderv/usdata && cd usdata
uv sync --extra pandas
uv run usdata info noaa:coops-water-levels
```

Run source examples from this checkout with `uv run usdata` (CLI) or
`uv run python` (Python). The pandas extra enables CSV reading; use `--extra radar`
or `--extra netcdf` for those formats. For contribution checks, continue with
[development setup](#development).

## Providers

Browse the [dataset catalog](docs/content/generated/catalog/index.md) for current support,
release availability, and dataset details. [Provider access notes](docs/content/providers/README.md)
explain agency-specific services; the [roadmap](docs/content/roadmap.md) describes priorities.

## Development

```sh
just setup
just check
```

See [development setup and commands](docs/content/project.md#development),
[contributing](CONTRIBUTING.md), and [architecture](docs/content/architecture.md).

## License

[Apache-2.0](LICENSE).
