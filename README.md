# usdata

Unified Python SDK and CLI for discovering, fetching, and tracking the
provenance of U.S. public scientific data (NOAA, USGS, NASA, and more).

> Status: pre-alpha. The data model, registry, and CLI exist; no provider
> adapter downloads data yet. See [docs/roadmap.md](docs/roadmap.md).

## Install

```sh
pip install usdata        # or: uv add usdata
```

## Usage

```python
from usdata import search, get

for r in search("radar", location="Oklahoma", start="2024-05-06", end="2024-05-07"):
    print(r.dataset.id, r.dataset.title)

ds = get("noaa:nexrad-level2")
print(ds.capabilities)
```

```sh
usdata search "tornado radar" --state OK
usdata info noaa:ghcn-daily
usdata fetch noaa:nexrad-level2 --lat 35.47 --lon -97.52 --start 2024-05-06T20:00 --end 2024-05-06T23:00
usdata pull dataset.yaml
```

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

Releases are published to PyPI by tagging: create a GitHub release and the
`publish.yml` workflow uploads via trusted publishing.

See [docs/architecture.md](docs/architecture.md) for how the pieces fit and
[docs/adr/](docs/adr/) for why.

## License

Apache-2.0
