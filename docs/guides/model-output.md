# Model output

HRRR and GFS files are whole GRIB2 archives of one model run at one forecast
hour. A query names the run; `open(select=...)` picks the fields.

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

The pitfall follows from that rule: `--start 2024-05-07 --end 2024-05-07`
spans only midnight, so with `cycle=4` it contains no run and is rejected. Give
the end a time, or use the next day.

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
time, and the summary then ends with `size unknown for N`. Add `--json` to get
the same asset records as a JSON array instead of columns.

## Selecting fields

A file holds hundreds of messages, so `open()` needs `select` with ecCodes key
names. Opening without it raises an error listing every
`(shortName, typeOfLevel, level)` in the file, which is the quickest way to
discover what a run contains:

```python
env = item.open(
    select={"shortName": ["cape", "hlcy"], "typeOfLevel": ["surface", "heightAboveGroundLayer"]}
)
```

Variables that share a `shortName` get the level appended to their names.
Grids are Lambert conformal for HRRR, with two-dimensional latitude and
longitude, and regular for GFS. Each dataset's guide lists verified keys for
the common severe-weather fields.

The [HRRR environment example](https://usdata.dev/examples/hrrr-environment/)
reads surface CAPE and 0–3 km helicity at the grid point nearest a tornado
report; the [GFS example](https://usdata.dev/examples/gfs-environment/) does
the same from the global analysis.
