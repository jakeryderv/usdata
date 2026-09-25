# Model output

HRRR and GFS files are whole GRIB2 archives of one model run at one forecast
hour. A query names the run; `open_grib2(select=...)` picks the fields.

```sh
usdata fetch noaa:hrrr -p cycle=20 -p forecast_hour=0 \
  --start 2024-05-06T20:00Z --end 2024-05-06T20:00Z --dry-run
```

## Runs, cycles, and forecast hours

The window selects runs by **initialization time**. `cycle` is the run's UTC
hour and is required: HRRR runs every hour, GFS at 00, 06, 12, and 18. A
window from 20:00 to 20:00 with `cycle=20` selects exactly that run; a
24-hour window selects the same cycle on two days. `forecast_hour` is an
integer or list; HRRR extends to 48 hours on the 00, 06, 12, and 18 UTC runs
and 18 otherwise, and GFS to 384 with the hourly-then-3-hourly schedule that
depends on `resolution`. Hours the run does not publish are rejected before
any request.

--8<-- "_snippets/utc-window.md"

So `--start 2024-05-07 --end 2024-05-07` is the whole of that day and selects
its `cycle` run, whichever hour that is. A window given with times must reach
the initialization hour: 20:00 to 20:00 with `cycle=4` contains no run and is
rejected before any request.

## Files and sizes

HRRR `file=sfc` is the 150 MB surface set with CAPE, helicity, winds, and
reflectivity; `prs` and `nat` are the 400 to 700 MB pressure and native sets.
GFS `resolution=1p00` is about 40 MB, `0p25` about 500 MB. Always dry-run
first; the listing prints the exact size in bytes between the asset id and its
href, and the total on stderr:

```text
hrrr.20240506.t20z.wrfsfcf00.grib2	150114757	s3://noaa-hrrr-bdp-pds/hrrr.20240506/conus/hrrr.t20z.wrfsfcf00.grib2
1 asset(s) matched, 150114757 bytes
```

The column is `?` for the datasets whose service reports no size at listing
time; the summary then reads `at least M bytes` and names the source that
withheld it, rather than implying a measured zero. Add `--json` to get the same
asset records as a JSON array instead of columns.

## Fetching only the fields you need

Add `messages` and the same query fetches byte ranges of the object instead of
all of it. Name the fields as the object's `.idx` sidecar names them, not as
the reader's `select` does:

```sh
usdata fetch noaa:hrrr -p cycle=20 -p forecast_hour=0 \
  -p messages="CAPE:surface,HLCY:3000-0 m above ground" \
  --start 2024-05-06T20:00Z --end 2024-05-06T20:00Z --dry-run
```

```text
hrrr.20240506.t20z.wrfsfcf00.part-13819cd0ccdf.grib2	1838460	s3://noaa-hrrr-bdp-pds/hrrr.20240506/conus/hrrr.t20z.wrfsfcf00.grib2#messages=105,131
1 asset(s) matched, 1838460 bytes
```

The same run without `messages` reports 150,114,757 bytes, so the two fields
cost about 1.2% of the file. The result is those messages concatenated, which
is a valid GRIB2 file: `open()` reads it without `select`, since the
fetch already selected. A manifest pins the byte ranges and the object's ETag
and restores from them without re-reading the index; because listing a
`messages` source resolves its ranges, `usdata pull dataset.yaml --dry-run`
prices such a source at the bytes the ranges cover, not at the whole object. Each provider guide lists
verified selectors:
[HRRR](../providers/noaa-hrrr.md#fetching-selected-messages),
[GFS](../providers/noaa-gfs.md#fetching-selected-messages).

## Selecting fields

A whole file holds hundreds of messages, so it is opened with `open_grib2(select=...)`
and ecCodes key names. Opening without it raises an error listing every
`(shortName, typeOfLevel, level)` in the file, which is the quickest way to
discover what a run contains:

```python
env = item.open_grib2(
    select={"shortName": ["cape", "hlcy"], "typeOfLevel": ["surface", "heightAboveGroundLayer"]}
)
```

Every variable is named `shortName_typeOfLevel_level` as soon as the select
spans more than one type of level or more than one level, and every variable
keeps its bare `shortName` when they all share one;
`attrs["usdata"]["messages"]` maps each name to its message. Grids are Lambert
conformal for HRRR, with two-dimensional latitude and longitude, and regular for
GFS. Each dataset's guide lists verified keys for the common severe-weather
fields.

The [HRRR environment example](https://usdata.dev/datasets/noaa/hrrr/)
reads surface CAPE and 0–3 km helicity at the grid point nearest a tornado
report; the [GFS example](https://usdata.dev/datasets/noaa/gfs/) does
the same from the global analysis.
