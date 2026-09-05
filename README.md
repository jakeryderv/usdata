# usdata

Unified Python SDK and CLI for discovering, fetching, and tracking the
provenance of U.S. public scientific data (NOAA, USGS, NASA, and more).

> Status: pre-alpha. `noaa:ghcn-daily` and `noaa:nexrad-level2` fetch real
> data with provenance; other registry entries are stubs.
> See [docs/roadmap.md](docs/roadmap.md).

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
usdata pull dataset.yaml
```

Fetched files land in `~/.cache/usdata/<provider>/<dataset>/` (override with
`USDATA_CACHE_DIR` or `--cache-dir`), each with a `.provenance.json` sidecar
recording source URL, retrieval time, checksum, size, and license.

A manifest declares every input a project needs; `pull` fetches them and writes
a lockfile with checksums and provenance so the inputs can be reproduced:

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

See [docs/architecture.md](docs/architecture.md) for how the pieces fit and
[docs/adr/](docs/adr/) for why.

## License

Apache-2.0
