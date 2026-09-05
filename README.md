# usdata

Unified Python SDK and CLI for discovering, fetching, and tracking the
provenance of U.S. public scientific data (NOAA, USGS, NASA, and more).

> Status: pre-alpha. `noaa:ghcn-daily` and `noaa:nexrad-level2` fetch real
> data with provenance. USGS daily values are available from source for the
> next release; other entries are stubs or planned.
> See [docs/roadmap.md](docs/roadmap.md).

## Providers

<!-- registry:start -->
| Provider | Available | Stub | Planned | Next up (0.5) | Datasets |
|---|---:|---:|---:|---|---|
| [NOAA](docs/providers/noaa.md) | 2 | 1 | 26 | `gsom`, `gsoy`, `storm-events`, `mrms`, `goes-abi`, `hurdat2`, `ibtracs`, `climate-normals`, `coops-water-levels`, `coastwatch-sst` | `ghcn-daily`, `nexrad-level2`, _coastwatch-sst_, +26 planned |
| [USGS](docs/providers/usgs.md) | 1 | 0 | 2 | — | `water-daily`, +2 planned |
| [Census Bureau](docs/providers/census.md) | 0 | 0 | 1 | — | +1 planned |
| [EPA](docs/providers/epa.md) | 0 | 0 | 1 | — | +1 planned |
| [FEMA](docs/providers/fema.md) | 0 | 0 | 1 | — | +1 planned |
| [NASA](docs/providers/nasa.md) | 0 | 0 | 1 | — | +1 planned |
| [USDA](docs/providers/usda.md) | 0 | 0 | 1 | — | +1 planned |

Available datasets are in `code`, stubs in _italics_; planned ones are counted. Each provider page has access notes and full dataset details; [docs/roadmap.md](docs/roadmap.md) lists datasets by target version.
<!-- registry:end -->

## Install

```sh
pip install usdata        # or: uv add usdata
```

## Usage

```python
from usdata import build_query, get, search
from usdata.fetch import fetch

for r in search("precipitation", location="Oklahoma"):
    print(r.dataset.id, r.dataset.title)

ds = get("noaa:ghcn-daily")
query = build_query(
    lat=35.39,
    lon=-97.60,
    radius_km=15,
    start="2024-05-06",
    end="2024-05-07",
    variables=["PRCP", "TMAX"],
)
for item in fetch(ds, query):
    print(item.path, item.provenance.checksum)
```

```sh
usdata search "tornado radar" --state OK
usdata info noaa:ghcn-daily
usdata fetch noaa:ghcn-daily --lat 35.39 --lon -97.60 --radius-km 15 \
    --start 2024-05-06 --end 2024-05-07 --vars PRCP,TMAX
usdata fetch noaa:ghcn-daily -p stations=USW00013967 --start 2024-01-01 --end 2024-12-31
usdata fetch noaa:nexrad-level2 --lat 35.47 --lon -97.52 \
    --start 2024-05-06T20:00 --end 2024-05-06T23:00        # nearest radar (KTLX)
usdata fetch noaa:nexrad-level2 -p site=KTLX --start 2024-05-06T20:00 --end 2024-05-06T20:30 --dry-run
usdata fetch usgs:water-daily -p sites=07164500 --vars 00060 \
    --start 2024-05-06 --end 2024-05-07                  # next release / source install
usdata pull dataset.yaml            # resolve, fetch, write dataset.lock.json
usdata verify dataset.yaml          # exit 1 if any cached input drifted
```

Fetched files land in `~/.cache/usdata/<provider>/<dataset>/` (override with
`USDATA_CACHE_DIR` or `--cache-dir`), each with a `.provenance.json` sidecar
recording source URL, retrieval time, checksum, size, and license.

Manifest and source fields are validated strictly; unknown fields are errors.
Provider-specific options belong under `params`.

A manifest declares every input a project needs. `pull` resolves each source,
fetches it, and writes `dataset.lock.json` pinning every asset with its checksum
and provenance. A second `pull` restores exactly what the lockfile pins without
re-querying upstream, so the inputs stay reproducible even if the source
changes. `verify` re-hashes the cached files against the lockfile. Editing the
manifest after locking requires `pull --force` to re-resolve.

```yaml
name: tornado-environment
sources:
  - dataset: noaa:nexrad-level2
    location: oklahoma
    start: 2024-05-06
    end: 2024-05-07
  - dataset: noaa:ghcn-daily
    location: oklahoma
    start: 2024-05-01
    end: 2024-05-31
```

## Development

Requires [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/).

```sh
git clone https://github.com/jakeryderv/usdata && cd usdata
just setup     # install toolchain and dependencies
just test      # unit tests
just check     # format, lint, typecheck, tests (what CI runs)
just run search radar
```

Integration tests that hit live services run with `just test-integration`.

Releases: `just release minor` opens a version-bump PR; merging it publishes
to PyPI and creates the tag and GitHub release. See
[docs/versioning.md](docs/versioning.md).

See [docs/providers/](docs/providers/) for per-provider access notes,
[docs/architecture.md](docs/architecture.md) for how the pieces fit,
[docs/adr/](docs/adr/) for why, and [CONTRIBUTING.md](CONTRIBUTING.md) to add
a dataset.

## License

Apache-2.0
