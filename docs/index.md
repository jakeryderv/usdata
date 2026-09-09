# Start with one dataset

usdata connects **discovery → fetch → local reading → reproducible inputs**.
The registry tells you which datasets are supported; adapters translate your
query to an upstream service; optional readers decode the downloaded format.

These docs describe this checkout, including features marked **Unreleased**.
Use the [changelog](../CHANGELOG.md) to check release availability.

## Install and discover

```sh
pip install usdata
usdata search precipitation --location Oklahoma
usdata info noaa:ghcn-daily
```

Search is local and ranks a curated catalog. It does not query every agency's
live catalog. Planned entries are not fetchable; see [provider coverage](providers/README.md).

## Fetch a small station query

```sh
usdata fetch noaa:ghcn-daily -p stations=USW00013967 \
    --start 2024-05-06 --end 2024-05-07 --vars PRCP,TMAX
```

Fetching needs network access. Files are cached under `~/.cache/usdata/` by
default, with source URLs, retrieval timestamps and checksums in provenance sidecars.

## Open the local result

Install `usdata[pandas]` for CSV reading, then use the same workflow in Python:

```python
from usdata import build_query, get
from usdata.fetch import fetch

items = fetch(
    get("noaa:ghcn-daily"),
    build_query(
        start="2024-05-06",
        end="2024-05-07",
        variables=["PRCP", "TMAX"],
        stations="USW00013967",
    ),
)
frame = items[0].open()
print(frame.head())
```

Reading is local. CSV, radar, and NetCDF4 have separate optional extras; see
[readers and their limits](reference/readers.md).

## Choose the next step

| Goal | Read next |
|---|---|
| Explore query options and CLI workflows | [Fetch and analyze](guides/fetch-and-analyze.md) |
| Repeat an analysis with pinned inputs | [Manifests and lockfiles](reference/manifests.md) |
| Learn through saved data and plots | [Runnable notebooks](../examples/README.md) |
| Understand a provider's query limits | [Provider access notes](providers/README.md) |
| Find an exact Python argument | [Python reference](reference/api.md) |
| Extend or contribute | [Contributing](../CONTRIBUTING.md) and [architecture](architecture.md) |

For local development and documentation preview, follow the canonical
[development setup](../README.md#development).
