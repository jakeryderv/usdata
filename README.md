# usdata

Unified Python SDK and CLI for discovering, fetching, and tracking the
provenance of U.S. public scientific data (NOAA, USGS, NASA, and more).

> Status: pre-alpha. v0.5 supports GHCN-Daily, NEXRAD Level II, USGS daily
> values, and CoastWatch SST subsets with provenance, plus Census state/county
> lookup. Other datasets are planned.
> See [docs/roadmap.md](docs/roadmap.md).

## Providers

<!-- registry:start -->
| Provider | Available | Stub | Planned | Next up (unassigned) | Datasets |
|---|---:|---:|---:|---|---|
| [NOAA](docs/providers/noaa.md) | 3 | 0 | 26 | — | `ghcn-daily`, `nexrad-level2`, `coastwatch-sst`, +26 planned |
| [USGS](docs/providers/usgs.md) | 1 | 0 | 2 | — | `water-daily`, +2 planned |
| [Census Bureau](docs/providers/census.md) | 0 | 0 | 1 | — | +1 planned |
| [EPA](docs/providers/epa.md) | 0 | 0 | 1 | — | +1 planned |
| [FEMA](docs/providers/fema.md) | 0 | 0 | 1 | — | +1 planned |
| [NASA](docs/providers/nasa.md) | 0 | 0 | 1 | — | +1 planned |
| [USDA](docs/providers/usda.md) | 0 | 0 | 1 | — | +1 planned |

Available datasets are in `code`, stubs in _italics_; planned ones are counted. Available means implemented in this source checkout; consult the [releases](https://github.com/jakeryderv/usdata/releases) for published support. Each provider page has access notes and full dataset details; [docs/roadmap.md](docs/roadmap.md) lists datasets by target version.
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
usdata search precipitation --location "Cleveland County, OK"
usdata info noaa:ghcn-daily
usdata fetch noaa:ghcn-daily --lat 35.39 --lon -97.60 --radius-km 15 \
    --start 2024-05-06 --end 2024-05-07 --vars PRCP,TMAX
usdata fetch noaa:ghcn-daily -p stations=USW00013967 --start 2024-01-01 --end 2024-12-31
usdata fetch noaa:nexrad-level2 --lat 35.47 --lon -97.52 \
    --start 2024-05-06T20:00 --end 2024-05-06T23:00        # nearest radar (KTLX)
usdata fetch noaa:nexrad-level2 -p site=KTLX --start 2024-05-06T20:00 --end 2024-05-06T20:30 --dry-run
usdata fetch usgs:water-daily -p sites=07164500 --vars 00060 \
    --start 2024-05-06 --end 2024-05-07
usdata fetch noaa:coastwatch-sst --bbox=-80.08,30.02,-80.02,30.08 \
    --start 2024-05-06T12:00Z --end 2024-05-06T12:00Z    # four grid cells
usdata pull dataset.yaml            # resolve, fetch, write dataset.lock.json
usdata verify dataset.yaml          # exit 1 if any cached input drifted
```

Fetched files land in `~/.cache/usdata/<provider>/<dataset>/` (override with
`USDATA_CACHE_DIR` or `--cache-dir`), each with a `.provenance.json` sidecar
recording source URL, retrieval time, checksum, size, and license.

Locations accept state names/postal codes, county/state names, and quoted FIPS
codes. These select bounding rectangles; see [place lookup](docs/reference/places.md)
for coverage, ambiguity, and antimeridian limits. CoastWatch CSV includes a
second header row containing units; see its [access notes](docs/providers/noaa.md#coastwatch-sst).

Manifest and source fields are validated strictly; unknown fields are errors.
Provider-specific options belong under `params`.

A manifest declares every input a project needs. `pull` resolves each source,
fetches it, and writes `dataset.lock.json` pinning every asset with its checksum
and provenance. A second `pull` restores exactly what the lockfile pins without
re-querying upstream, so the inputs stay reproducible even if the source
changes. `verify` checks the manifest checksum and re-hashes cached files
against the lockfile. Editing the manifest after locking requires `pull --force`
to re-resolve. A required source matching no assets fails the pull; set
`allow_empty: true` on a source only when an empty result is intentional.

Checksums detect upstream changes; they cannot recover historical bytes that
are no longer available. Preserve the cache for long-lived reproducibility.
See the [manifest reference](docs/reference/manifests.md) and the small
[NOAA/USGS example](examples/weather-and-streamflow/README.md).

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

## Opening CSV data (next release)

`FetchedAsset.open()` is available from source for v0.6 with the optional pandas
extra. It reads cached CSV into a DataFrame, preserves identifier strings, and
keeps CoastWatch units as metadata. See the [reader reference](docs/reference/readers.md)
and [fetch → open → analyze example](examples/sst-analysis/README.md).

## Development

Requires [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/).

```sh
git clone https://github.com/jakeryderv/usdata && cd usdata
just setup     # install toolchain and dependencies
just test      # unit tests
just check     # format, lint, typecheck, offline tests, generated docs, release notices
just check-pandas  # install the CSV extra and run the same checks
just build     # build wheel and sdist
just smoke     # exercise core and pandas wheel installations outside the checkout
just run search radar
```

Unit tests mechanically block network connections. Integration tests that hit
live services run with `just test-integration`. CI checks Python 3.11 and 3.14 on
Linux, both with and without pandas, and smoke-tests both installed-wheel
profiles on Linux, macOS, and Windows. The full unit and live-service suites currently run on Linux. `just setup` restores
a core-only development environment; `just check-pandas` installs the extra.

Releases: `just release minor` opens a version-bump PR; merging it publishes
to PyPI and creates the tag and GitHub release. See
[docs/versioning.md](docs/versioning.md).

See [docs/providers/](docs/providers/) for per-provider access notes,
[docs/architecture.md](docs/architecture.md) for how the pieces fit,
[docs/adr/](docs/adr/) for why, and [CONTRIBUTING.md](CONTRIBUTING.md) to add
a dataset.

## License

Apache-2.0
