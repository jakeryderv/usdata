# Fetch and analyze

New to usdata? Start with [getting started](../getting-started.md). This guide
covers the everyday fetch loop; pinning inputs for later is in
[pin inputs](pin-inputs.md).

## Fetch near a place, dry run first

```sh
usdata fetch noaa:ghcn-daily --lat 35.39 --lon -97.60 --radius-km 15 \
  --start 2024-05-06 --end 2024-05-07 --vars PRCP,TMAX --dry-run
```

`--dry-run` contacts the provider to list what the query resolves to, with
sizes where the service reports them, and downloads nothing. Remove it to
fetch. Pass shared options through their own flags, `--start`, `--end`,
`--location`, `--bbox`, `--vars`, and provider-specific selectors through
`-p key=value`, for example `-p stations=USW00013967`. For exact stations, use
the dataset's id option rather than geographic discovery; a place is a
rectangle, not a boundary.

--8<-- "_snippets/utc-window.md"

## The same query from Python

```python
from usdata import build_query, fetch, get

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
    frame = item.open()
```

`fetch` returns one item per asset with its cached path and provenance.
`item.provenance.source_url` records the URL the bytes were actually fetched
from and `item.asset.href` records where the listing pointed, which are equal
today but need not stay equal.
`item.inspect()`, or `usdata inspect <path>`, summarizes what a fetched file
holds before you open it: CSV columns and row count with no extra installed,
NetCDF4 variables or GRIB2 messages with the format's extra.
`open()` is a separate local step that needs the reader extra for the format;
without it you still have the path. What each reader returns is in
[readers](../concepts/readers.md), and the options in the
[reader reference](../reference/readers.md).

## Where files go

Files live under `~/.cache/usdata/` unless `USDATA_CACHE_DIR` or `--cache-dir`
says otherwise, with a provenance sidecar beside each. A repeated query is a
cache hit checked against that sidecar; `--force` re-downloads and `usdata verify`
re-reads the bytes.

On a terminal, fetch reports resolved counts, known sizes, download progress,
and verified cache hits on stderr. `--no-progress` disables it, and redirecting
output disables it automatically.

The [SST example](https://usdata.dev/examples/sst-analysis/) fetches a small
gridded CSV and opens it with units;
[monthly climate](https://usdata.dev/examples/monthly-climate/) does the same
for station summaries.
