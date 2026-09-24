# Radar and satellite

Radar volumes, satellite scenes, and lightning files arrive every few minutes
and are fetched whole. The work is choosing the right file, then opening only
what you need.

```python
from datetime import UTC, datetime, timedelta

from usdata import build_query, fetch, get, select_by_time
from usdata.providers import load_adapter

dataset = get("noaa:nexrad-level2")
target = datetime(2024, 5, 7, 4, 39, tzinfo=UTC)
window = build_query(start=target - timedelta(minutes=10), end=target, site="KTLX")
with load_adapter(dataset) as adapter:
    volumes = adapter.list_assets(window)
choice = select_by_time(
    volumes, target=target, tolerance=timedelta(minutes=5), direction="at_or_before"
)
start = choice.asset.time.start
(item,) = fetch(dataset, build_query(start=start, end=start, site="KTLX"))
radar = item.open(sweep=0)
```

## Level II volumes

A geographic query picks the nearest radar; `site=KTLX` names one. Windows
are inclusive UTC start times, at most 31 days, and a volume is roughly 10 to
20 MB compressed and far larger decoded, so open one sweep at a time with
`sweep=`. The reader checks that the file's moment and coordinate records
align before decoding and raises `RadarDecodeError` for a sweep it cannot
place; choose another sweep rather than trusting a partial volume.

## GOES ABI scenes

Name the satellite and channel; the window selects CONUS scans by start time,
at most seven days, and a week of one channel is about 2,000 scenes, so keep
it to minutes. Channel 13 brightness temperature is the usual choice for storm
tops. The netcdf extra returns the scene with its projection metadata and
quality flags; masking on the flags is yours to do.

## GLM lightning

GLM files are 20-second detection tables for the satellite's whole field of
view, 180 an hour, so the window is at most one day and a few minutes around
an event is the useful size. Open with the netcdf extra and flatten the flash
table with `ds[columns].reset_coords()[columns].to_dataframe()`, keeping the
flash position and time coordinates as columns; then filter by latitude and
longitude yourself.

## Choosing a file by time

`select_by_time` picks among assets you listed, with a target, a tolerance,
and a direction. `at_or_before` means the file started by then, not that it
had finished scanning. Save the selection's JSON beside the analysis; see
[time and place](../concepts/time-and-place.md).

--8<-- "_snippets/large-grids.md"

The [event-context example](https://usdata.dev/studies/event-context/) does
all of this for one Storm Events report: nearest KTLX volume, nearest GOES-16
scene, explicit UTC conversion, one safe sweep, and a locked restore.
