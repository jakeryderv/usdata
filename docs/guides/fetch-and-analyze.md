# Fetch and analyze data

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

Storm Events bulk access is available since v0.8. Dates select complete
annual details archives; filter rows locally after opening the gzip CSV. For example:

```sh
usdata fetch noaa:storm-events --start 2024-05-01 --end 2024-05-31 --dry-run
```

This lists the entire 2024 archive. Location and variable filters are rejected;
see the [executed Storm Events notebook](../../examples/storm-events/example.ipynb)
for local filtering and reporting limitations.

Fetched files land in `~/.cache/usdata/<provider>/<dataset>/` (override with
`USDATA_CACHE_DIR` or `--cache-dir`), each with a `.provenance.json` sidecar
recording source URL, retrieval time, checksum, size, and license.

Locations accept state names/postal codes, county/state names, and quoted FIPS
codes. These select bounding rectangles; see [place lookup](../reference/places.md)
for coverage, ambiguity, and antimeridian limits. CoastWatch CSV includes a
second header row containing units; see its [access notes](../providers/noaa.md#coastwatch-sst).

Manifest and source fields are validated strictly; unknown fields are errors.
Provider-specific options belong under `params`.

For already-listed assets, `select_by_time` selects a scan start using an explicit
tolerance and nearest/prior direction (Unreleased). It returns the chosen asset,
signed offset, and candidate counts, including an explicit no-match result. See
[temporal selection](../reference/selection.md) and the
[event-context notebook](../../examples/event-context/example.ipynb).

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
See the [manifest reference](../reference/manifests.md) and the small
[NOAA/USGS example](../../examples/weather-and-streamflow/README.md).

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

Terminal progress is available since v0.7. On a terminal, `fetch` and
`pull` show progress on stderr: resolved asset counts,
known bytes and unknown sizes, HTTP download bytes for the current attempt, and
validated cache hits. `fetch --dry-run` also summarizes known sizes. Asset totals
include possible cache hits; each manifest source is resolved separately. Bytes
from a failed HTTP attempt reset on retry; encoded responses have unknown decoded
size. Adapters that assemble files from metadata requests show asset-level progress.
Use `--no-progress` to disable it. Progress is automatically disabled when either
stdout or stderr is redirected; existing output lines and exit codes are unchanged.

For single-channel GOES CONUS imagery (available since v0.8):

```sh
usdata fetch noaa:goes-abi --start 2024-05-06T12:01:18.1Z --end 2024-05-06T12:01:18.1Z -p satellite=18 -p channel=6
```

The download is a whole NetCDF scene. See [GOES access notes](../providers/noaa.md#goes-abi-conus-imagery)
for supported selectors and scan-start time semantics.

## Opening CSV data

`FetchedAsset.open()` is available since v0.6 with the optional pandas
extra (`pip install "usdata[pandas]"`). It reads cached CSV into a DataFrame,
preserves identifier strings, and keeps CoastWatch units as metadata.
See the [reader reference](../reference/readers.md)
and [fetch → open → analyze example](../../examples/sst-analysis/README.md).

The [examples directory](../../examples/README.md) contains executed Jupyter notebooks
with saved data previews, small plots, and source provenance. Start with weather
and streamflow for manifest workflows, SST for gridded CSV reading, or monthly
climate for GSOM observations.

NetCDF4 scene opening is available since v0.8 with `usdata[netcdf]`.
See the executed [GOES infrared notebook](../../examples/goes-imagery/example.ipynb).

