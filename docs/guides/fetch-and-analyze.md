# Fetch and analyze data

New to usdata? Start with the [one-dataset walkthrough](../index.md).
These recipes cover the next common tasks. Dataset-specific selectors and
scientific limits live in the [provider guides](../providers/README.md).

## Find data near a place

```sh
usdata search precipitation --location "Cleveland County, OK"
usdata info noaa:ghcn-daily
usdata fetch noaa:ghcn-daily --lat 35.39 --lon -97.60 --radius-km 15 \
  --start 2024-05-06 --end 2024-05-07 --vars PRCP,TMAX --dry-run
```

Search ranks the local curated catalog. `info` shows capabilities and status;
`fetch --dry-run` contacts the provider to list assets without downloading them.
Remove `--dry-run` to fetch. For exact stations, use the dataset's station ID
option instead of geographic discovery. Use `--param` only for provider-specific
selectors such as `-p stations=USW00013967`; pass shared query options through
their flags, such as `--start`, `--location`, and `--vars`.

Place names and FIPS codes select bounding rectangles, not precise administrative
boundaries. See [place lookup](../reference/places.md) for ambiguity and limits.
Time selection also varies: a station query may return selected days, while
Storm Events returns whole annual files and GOES returns whole scenes.

## Use the same query from Python

```python
from usdata import build_query, get
from usdata.fetch import fetch

query = build_query(
    lat=35.39,
    lon=-97.60,
    radius_km=15,
    start="2024-05-06",
    end="2024-05-07",
    variables=["PRCP", "TMAX"],
)
for item in fetch(get("noaa:ghcn-daily"), query):
    print(item.path, item.provenance.checksum)
```

Opening is a separate local step: `item.open()` uses an optional format reader.
Install `usdata[pandas]` for CSV, `usdata[radar]` for NEXRAD, or `usdata[netcdf]`
for NetCDF4. See [reader behavior and limits](../reference/readers.md).
For already-listed radar/GOES assets, [temporal selection](../reference/selection.md)
chooses a scan start using an explicit tolerance and nearest/prior direction.

## Keep and refresh reproducible inputs

Declare inputs in a [manifest](../reference/manifests.md), then run:

```sh
usdata pull dataset.yaml --cache-dir .data
usdata verify dataset.yaml --cache-dir .data
```

The first pull resolves and downloads inputs, then writes `dataset.lock.json`.
Subsequent pulls restore those pinned assets without repeating discovery.
`verify` checks the manifest and local file checksums offline. Commit the manifest
and lockfile; preserve `.data` separately because a checksum cannot recover bytes
that upstream no longer serves.

If an agency revises data behind a pinned URL, pull exits 4 and lists every
changed asset without touching the lockfile. Accept the new bytes for just those
entries with `usdata pull dataset.yaml --update noaa:ghcn-daily --cache-dir .data`,
naming an asset id or dataset id. Use `usdata pull dataset.yaml --force --cache-dir .data`
only when intentionally refreshing the source selection itself. Editing the
manifest requires this explicit refresh. Required sources must resolve to assets;
`allow_empty: true` permits an intentionally empty resolution, not a failed download.

Without an explicit cache directory, files live under `~/.cache/usdata/`; override
this with `USDATA_CACHE_DIR`. Provenance sidecars record the source URL, retrieval
time, checksum, byte count, and license.

## Inspect download progress

On a terminal, fetch and pull report resolved asset counts, known byte sizes,
download progress, and validated cache hits on stderr. Some APIs assemble results
without advertising a size. Retried downloads restart their byte counter.
Use `--no-progress` to disable progress; redirection disables it automatically.

## Pick an analysis example

The [examples index](../examples/README.md) distinguishes executed notebooks
from manifest recipes. Start with weather and streamflow for reproducible inputs,
SST for a small gridded CSV, or monthly climate for station summaries. Saved
notebook results are snapshots; running them again contacts live services.
