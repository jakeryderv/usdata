# Start with one dataset

usdata connects **discovery → fetch → local reading → reproducible inputs**.
The registry tells you which datasets are supported; adapters translate your
query to an upstream service; optional readers decode the downloaded format.

These docs describe this checkout, including features marked **Unreleased**.
Use the [changelog](../CHANGELOG.md) to check release availability. The walkthrough
below works with the published package. For upcoming features, follow the
[source installation](../README.md#source-installation).

## Install and discover

Use an activated Python 3.11+ virtual environment:

```sh
python -m pip install "usdata[pandas]"
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

The pandas extra installed above opens CSV files. Run this in a Python script
or interpreter in the same environment:

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

## Preserve the inputs

Save this as `dataset.yaml` to repeat the same station query:

```yaml
name: first-station
sources:
  - dataset: noaa:ghcn-daily
    start: 2024-05-06
    end: 2024-05-07
    variables: [PRCP, TMAX]
    params:
      stations: USW00013967
```

```sh
usdata pull dataset.yaml
usdata verify dataset.yaml
```

The first pull writes `dataset.lock.json`; later pulls restore its pinned assets.
To try restoration into a new cache, choose an empty directory:

```sh
usdata pull dataset.yaml --cache-dir restored-data
usdata verify dataset.yaml --cache-dir restored-data
```

Keep the same manifest and lockfile. Pull downloads missing pinned files;
verification checks local bytes without network access. Use the same cache
directory for both commands. An upstream revision can cause restoration to fail
with a checksum mismatch.

Commit the manifest and lockfile and back up the cached bytes. Lockfiles detect
changed data but cannot recover an upstream version that is no longer available.
See [manifest behavior](reference/manifests.md) before intentionally refreshing inputs.

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
