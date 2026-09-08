# Monthly airport climate

Available since v0.7. This example fetches May 2024 precipitation
and mean temperature at Will Rogers World Airport in Oklahoma City, writes a
manifest lockfile, and opens the CSV with optional pandas support.

Follow [development setup](../../README.md#development), then run from the repo root:

```sh
uv sync --all-groups --extra pandas
uv run --extra pandas python examples/monthly-climate/analyze.py
uv run usdata verify examples/monthly-climate/dataset.yaml
```

The manifest requests `units: metric`, so `PRCP` is millimeters and `TAVG` is
degrees Celsius. NCEI CSV does not carry a units row: the reader retains the
source URL in `frame.attrs["usdata"]["provenance"]`, but does not invent a units map.
Station IDs stay strings and `DATE` stays `YYYY-MM`; each record represents
a whole calendar month. Missing values remain missing.

Running again uses the lockfile and cached bytes. To exercise restoration, delete
the downloaded CSV and rerun. Pull reuses the pinned URL and checks the original
checksum; revised upstream data causes a checksum error. Keep the cache if you
need a durable archive. The generated example lockfile is ignored in this checkout.

All UTC calendar months touched by the requested interval are selected in full.
For example, May 6–7 still selects May, while May 31–June 1 selects both months.
See [NOAA access notes](../../docs/providers/noaa.md#global-summary-of-the-month)
for geographic queries and the bounded probes used to validate this adapter.
