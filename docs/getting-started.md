# Getting started

usdata connects **discovery → fetch → local reading → reproducible inputs**.
The registry tells you which datasets are supported; adapters translate your
query to an upstream service; optional readers decode the downloaded format.

This walkthrough works with the published package and takes a few minutes.
It fetches one small file, opens it, pins it in a manifest, and restores it
into a fresh cache.

## Install and discover

Use an activated Python 3.11+ virtual environment:

```sh
python -m pip install "usdata[pandas]"
usdata search precipitation --location Oklahoma
usdata info noaa:ghcn-daily
```

Search is local and ranks a curated catalog. It does not query every agency's
live catalog. Use the [searchable dataset browser](https://usdata.dev/datasets/)
to compare formats, required inputs, and examples.

--8<-- "_snippets/planned-datasets.md"

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
from usdata import build_query, fetch, get

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

Reading is local. Each format has its own optional extra; see
[readers](concepts/readers.md).

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

Once the inputs are pinned, `usdata cite dataset.yaml` prints the citation for
every dataset in the lockfile, with the retrieval dates and checksummed asset
counts a methods section needs (`--format bibtex` for a bibliography).

Commit the manifest and lockfile and back up the cached bytes. Lockfiles detect
changed data but cannot recover an upstream version that is no longer available.
See [manifests and lockfiles](concepts/manifests.md) before intentionally refreshing inputs.

## Choose the next step

| Goal | Read next |
|---|---|
| Choose a dataset | [Find a dataset](guides/find-a-dataset.md) |
| Explore query options and the fetch loop | [Fetch and analyze](guides/fetch-and-analyze.md) |
| Repeat an analysis with pinned inputs | [Pin inputs](guides/pin-inputs.md) |
| Cite the inputs in a methods section | [Cite what you used](concepts/manifests.md#cite-what-you-used) |
| Learn through saved data and plots | [Examples](https://usdata.dev/examples/) |
| Understand a provider's query limits | [Provider notes](providers/README.md) |
| Find an exact Python argument | [Python API](reference/api.md) |

Installation options, extras, and the source checkout are on the
[Install](install.md) page.
