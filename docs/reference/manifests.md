# Manifest schema

What manifests, lockfiles, pull, and verify do is explained in
[manifests and lockfiles](../concepts/manifests.md). This page is the schema,
the provider options, and the numbers.

## Manifest fields

```yaml
name: weather-and-streamflow
version: "1.0"
sources:
  - dataset: noaa:ghcn-daily
    start: 2024-05-06
    end: 2024-05-07
    variables: [PRCP, TMAX]
    params:
      stations: USW00013967
      units: metric
```

| Field | Meaning |
|---|---|
| `name` | Required project or input-set name. |
| `version` | Manifest format label, default `"1.0"`. Informational; not the package or dataset version. |
| `sources` | Required, non-empty list of source specifications. |

Each source accepts:

| Field | Meaning |
|---|---|
| `dataset` | Required registry id, such as `usgs:water-daily`. |
| `location` | A place name, postal code, or quoted FIPS code; see the [places reference](places.md). Mutually exclusive with `bbox`. |
| `bbox` | WGS84 box with `west`, `south`, `east`, `north`. |
| `start`, `end` | ISO dates or datetimes. Most adapters require both; climate normals make them optional and HURDAT2 rejects them. |
| `variables` | Dataset-specific variable names or codes. Quote numeric codes to keep leading zeros. |
| `params` | Provider-specific options from the table below. Unknown keys are errors. |
| `allow_empty` | Default `false`. `true` only when this source may legitimately resolve to no assets. |

Unknown manifest and source fields are rejected. `params` must not repeat
`location`, `bbox`, `start`, `end`, or `variables`. Empty explicit id lists are
invalid even with `allow_empty: true`.

## Provider options

`usdata info <dataset>` prints each dataset's parameter names with a one-line
description read from the adapter. This table adds what does not fit on one
line.

| Dataset | `params` | Variables and time |
|---|---|---|
| `noaa:ghcn-daily` | `stations`: non-empty comma-separated string or list; otherwise requires a geographic query. `units`: `metric` (default) or `standard`. Explicit stations take precedence over geographic selection. | Names such as `PRCP`, `TMAX`; inclusive calendar dates, time of day ignored. |
| `noaa:gsom` | `stations`: non-empty comma-separated string or list, or a geographic query; do not combine them. `units`: `metric` (default) or `standard`. | Names such as `PRCP`, `TAVG`; every UTC calendar month touched by the interval is selected in full. |
| `noaa:gsoy` | `stations`: non-empty comma-separated string or list, or a geographic query; do not combine them. `units`: `metric` (default) or `standard`. | Names such as `PRCP`, `TAVG`; every UTC calendar year touched is selected in full. Annual labels do not imply identical accumulation seasons for all elements. |
| `noaa:lcd` | `stations`: eleven-digit ids, comma-separated or a list, or a geographic query. `units`: `metric` (default) or `standard`. | Optional column filters; every report on whole calendar days per station. |
| `noaa:climate-normals` | `period`: `monthly` (default), `daily`, or `annualseasonal`. `stations` or a geographic query; do not combine them. `units`: `metric` (default) or `standard`. | NCEI data type codes such as `MLY-TMAX-NORMAL`; unknown codes yield empty columns. Dates optional. For daily and monthly, both dates select a month-day window inside placeholder year 2020 and may not cross the new year; annualseasonal rejects dates. Asset time bounds are the 1991-2020 normals period. |
| `noaa:nexrad-level2` | `site` or `sites`: radar ids, mutually exclusive. Alternatively `nearest`: positive integer with a geographic query. Do not combine `nearest` with explicit ids. | Whole scans, no variable subsetting. Inclusive UTC window of at most 31 days. |
| `noaa:nexrad-level3` | Level II site selection plus required `products`: comma-separated or list of product codes from the allowlist. | Whole product files; inclusive UTC window of at most 31 days, not before 2020-03-30. |
| `noaa:goes-abi` | Required `satellite`: 16, 17, 18, or 19, and `channel`: 1–16 or `C01`–`C16`. Optional `product`: only `ABI-L2-CMIPC`. Geographic selection is rejected. | Whole single-channel CONUS scenes selected by inclusive UTC scan-start time; at most seven days. Variable subsetting is rejected; select a channel. |
| `noaa:goes-glm` | Required `satellite`: 16, 17, 18, or 19. Geographic selection is rejected. | Whole 20-second files selected by inclusive UTC start time; at most one day. |
| `noaa:mrms` | Required `product`: one directory name from the allowlist, case-sensitive. | Whole two-minute CONUS grids selected by inclusive UTC stamp; at most one day; not before 2020-10-14. |
| `noaa:hrrr` | Required `cycle` (0–23) and `forecast_hour` (integer, list, or comma-separated; 0–48 on the 00, 06, 12, and 18 UTC runs, 0–18 otherwise). `file`: `sfc` (default), `prs`, or `nat`. | The window selects runs by initialization time, inclusive, at most one day. |
| `noaa:gfs` | Required `cycle` (0, 6, 12, or 18) and `forecast_hour` (0–384; hourly to 120 then every 3 hours at 0p25, every 3 hours at 0p50 and 1p00). `resolution`: `0p25` (default), `0p50`, or `1p00`. | The window selects runs by initialization time, inclusive, at most one day. |
| `noaa:coops-water-levels` | Required string `station` (seven digits) and `datum`; optional `units`: `metric` or `english`. | Six-minute observations. Both bounds required, UTC, minute precision, inclusive, at most 28 days. No geographic, text, or variable selection. No-data responses fail on fetch; `allow_empty` cannot suppress them. |
| `noaa:coops-tide-predictions` | As water levels, plus `interval`: `6` (default), `1`, `5`, `10`, `15`, `30`, `60`, `h`, or `hilo`. | Both bounds required, UTC, minute precision, inclusive, at most 366 days. |
| `noaa:storm-events` | None. | Both dates required; every UTC calendar year touched selects its latest annual details archive in full. Variable subsetting is rejected; filter rows locally. |
| `noaa:spc-tornado-reports` | None. | Both dates required; every year touched selects the narrowest file covering it (annual from 2008, half-decade and decade files before). |
| `noaa:hurdat2` | `basin`: `atlantic` (default) or `pacific`, case-insensitive. No geographic selection. | The newest revision of one whole basin file. Dates are rejected; filter track points locally. |
| `noaa:coastwatch-sst` | Requires a bbox or location. `stride`: positive integer, default 1, subsamples both spatial axes. At most 1,000,000 grid rows per request. | `analysed_sst` (default), `analysis_error`, `sea_ice_fraction`, `mask`. Inclusive UTC timestamps. |
| `usgs:water-daily` | `site` or `sites`: quoted monitoring ids, mutually exclusive, or a geographic query; explicit sites and a geographic filter both apply. `statistic_id`: quoted five-digit code, default `"00003"` (daily mean). | Quoted parameter codes such as `"00060"`; inclusive local calendar dates. |

Plural `stations` and `sites` accept strings or lists of strings. CO-OPS
`station` takes one seven-digit string, not a list. Radar ids are
case-insensitive; USGS ids may carry the `USGS-` prefix. Dataset-specific
behaviour, units, and limits are in the [provider notes](../providers/README.md).

## Pull, refresh, and restore

| Command | Effect |
|---|---|
| `usdata pull dataset.yaml` | Resolve and download, writing `dataset.lock.json`; with a lockfile, restore its pins. |
| `usdata pull dataset.yaml --cache-dir DIR` | Use `DIR` instead of the default cache; restoration on another machine. |
| `usdata pull dataset.yaml --update ID [--update ID]` | Accept new upstream bytes for the named asset or dataset ids only; rewrites only those pins. Exit 2 if a selector matches nothing, if combined with `--force`, or without a lockfile. |
| `usdata pull dataset.yaml --force` | Re-resolve every source and replace the lockfile. Required after any edit to the manifest. |
| `usdata verify dataset.yaml [--cache-dir DIR]` | Offline check of the manifest checksum and every cached file against the lockfile. |
| `usdata fetch ... --force` | Re-download one query even when the cache has a valid copy. |

In Python, `pull()` and `verify()` take `pathlib.Path` manifest arguments, not
strings; `pull(update=[...])` selects entries and raises `UpstreamChanged`
with a `drift` list when unaccepted changes remain. Exit codes are listed in
[how it works](../concepts/how-it-works.md#cli-exit-codes).

## Failures and retries

GET requests retry transient connection, timeout, and remote protocol
failures, and HTTP 429, 500, 502, 503, and 504, for at most three attempts,
with backoff of 0.5 then 1 second. `Retry-After` seconds and HTTP dates are
respected; a requested wait over 30 seconds is surfaced as an error instead of
retried early. Interrupted downloads restart from the beginning in a temporary
file. Permanent HTTP errors, local filesystem failures, and checksum mismatches
are not retried.
