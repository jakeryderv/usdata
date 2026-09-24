# For one Oklahoma tornado, do the two report archives agree on when and where it was, and what did radar, lightning, and the model analysis show at that place and time?

Open the [executed notebook](severe-weather-case-study.ipynb) to take one tornado report out of the
2024 Storm Events archive, confirm it against the Storm Prediction Center's own
2024 tornado file, and then ask the nearest KTLX Level II volume, five MRMS
mid-level rotation grids, twenty minutes of GOES-16 lightning, and the last HRRR
analysis before the report what each of them recorded at that time and place. The
answer measures agreement between two publication paths for one storm survey, and
what four remote-sensing and model products held within 25 km of the reported
path start. It does not detect a tornado in any of those products, it does not
establish that any of these quantities precede tornadoes in general, and it is
one case. See [examples setup](https://usdata.dev/studies/) to run it.

Available since v0.18.0, which adds fetching only the
GRIB2 messages a source names, `usdata pull --dry-run`, the Storm Events
`BEGIN_UTC` and `END_UTC` columns, and GRIB2 variable names that follow from the
select rather than from which short names collided. The named manifest sources
this example is built on, `FetchedAsset.inspect()`, registry-filled units, and
`usdata cite` are available since v0.17.0. The retained
[manifest](dataset.yaml) holds six named sources, and the notebook addresses each
one through `result.by_source["..."]`:

| Source | Dataset | What it pins | Assets | Bytes |
|---|---|---|---|---|
| `reports` | `noaa:storm-events` | The whole 2024 annual details archive, selected by a 2024-05-06 window | 1 | 12,693,243 |
| `spc` | `noaa:spc-tornado-reports` | The whole `2024_torn.csv` file | 1 | 230,094 |
| `radar` | `noaa:nexrad-level2` | Every KTLX volume scan between 04:34 and 04:46 UTC on 2024-05-07 | 2 | 39,708,043 |
| `rotation` | `noaa:mrms` | `RotationTrackML30min_00.50` grids stamped 04:34 to 04:42 UTC | 5 | 926,976 |
| `lightning` | `noaa:goes-glm` | GOES-16 GLM files starting 04:29:00 to 04:48:59 UTC | 60 | 29,536,150 |
| `environment` | `noaa:hrrr` | The CAPE and 0-3 km helicity messages of forecast hour 0 of the 04 UTC run, surface file | 1 | 1,765,823 |

That is **84,860,329 bytes, 84.9 MB, across 70 assets**. The live pull took
16.1 seconds and the whole notebook ran in 38 seconds. Nothing is subsetted on
the server: Storm Events and SPC arrive as whole annual tables, MRMS and GLM as
whole CONUS and full-disk files. Only the HRRR source is narrowed
before it is downloaded, and that is the client asking S3 for two byte ranges it
found in the object's index, not a service subsetting a file: the `messages`
selectors `CAPE:surface` and `HLCY:3000-0 m above ground` cost 1,765,823 bytes of
a 133,253,838 byte object, and both fields still arrive on the whole 3 km CONUS
grid. Every spatial narrowing happens locally.

`usdata pull dataset.yaml --dry-run` prices the whole manifest before anything
is pulled: one line per asset in the same columns `fetch --dry-run` uses, a
subtotal per source, and the total on stderr. Downloading nothing, it reads the
same YAML the pull reads, so the queries cannot drift from the ones being priced.
Trimmed here to the six subtotals and three of the seventy asset lines:

```text
$ usdata pull dataset.yaml --dry-run
StormEvents_details-ftp_v1.0_d2024_c20260728.csv.gz	12693243	https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/StormEvents_details-ftp_v1.0_d2024_c20260728.csv.gz
reports (noaa:storm-events): 1 asset(s), 12693243 bytes
2024_torn.csv	?	https://www.spc.noaa.gov/wcm/data/2024_torn.csv
spc (noaa:spc-tornado-reports): 1 asset(s), at least 0 bytes; size unknown for 1 asset(s)
radar (noaa:nexrad-level2): 2 asset(s), 39708043 bytes
rotation (noaa:mrms): 5 asset(s), 926976 bytes
lightning (noaa:goes-glm): 60 asset(s), 29536150 bytes
hrrr.20240507.t04z.wrfsfcf00.part-13819cd0ccdf.grib2	1765823	s3://noaa-hrrr-bdp-pds/hrrr.20240507/conus/hrrr.t04z.wrfsfcf00.grib2#messages=105,131
environment (noaa:hrrr): 1 asset(s), 1765823 bytes
6 source(s), 70 asset(s), at least 84630235 bytes; size unknown for 1 asset(s) from spc; nothing downloaded
```

The HRRR line is the partial asset: a `.part-` digest of the resolved message
numbers in the id, the byte total of those two ranges, and the object it was cut
from with a `#messages=105,131` fragment. The `at least` in the total, and the
named source after it, are the command reporting that the SPC page publishes no
size for `2024_torn.csv`; its real 230,094 bytes are what separate the priced
84,630,235 from the 84,860,329 the pull writes.

Report 1184052 is the same Oklahoma County tornado the six smaller severe-weather
examples use. Those examples paste its time and position in as constants to stay
small. This one puts the annual archive in the manifest instead, so the UTC start
time, the coordinates, the EF rating, and the path come out of the file, and
every window below is measured against a number the notebook derived.

The caveats that matter for the answer:

- **Storm Events and SPC are not independent.** Both publish the same NWS Storm
  Data entry, which is why the start time, the coordinates, the rating, the
  2.2 mile path length, and the 75 yard width match exactly rather than closely.
  The comparison shows that one survey survived two publication paths intact.
  The provider notes say the two databases share no identifier, so the match is
  made on local date, whole-track rows, and distance from the derived point.
- **Times come from three different clocks.** Storm Events timestamps are local,
  labelled by a `CZ_TIMEZONE` string, `CST-6` here. SPC rows are Central Standard
  Time for every tornado in the country, whatever zone it was in. Everything else
  is UTC. The pandas reader derives `BEGIN_UTC` and `END_UTC` from the Storm
  Events label and records the rule it used in
  `attrs["usdata"]["derived"]`; the SPC file has no such column, so that one the
  notebook still converts with an explicit fixed offset after checking the row's
  `tz` code.
- **The radar volume is chosen, not pinned.** The manifest asks KTLX for a twelve
  minute window, which resolves to two volume scans, and the notebook keeps the
  one whose scan start is nearest the derived report time. That scan begins 113
  seconds after the report and its rays span about sixteen seconds, so it is near
  the report rather than simultaneous with it. The beam centre over the report
  sits about 0.24 km above the radar, 24.61 km away.
- **MRMS values are half-hour maxima, not observations at the stamp.** Each grid
  holds the largest mid-level azimuthal shear in the thirty minutes ending at its
  file stamp, so the grid stamped 04:42 covers 04:12 to 04:42 and the peak in it
  is somewhere in that window. Values are quantized to whole units of
  0.001 s-1, so cells tie; the notebook counts ties and averages tied positions
  rather than letting array order pick one. Mid-level shear samples the 3 to 6 km
  layer, above a tornado, and its magnitude depends on radar range and viewing
  angle.
- **The 25 km radius is an analysis choice.** It is written into the notebook, not
  supplied by the package, and a different radius moves every maximum in the
  tables.
- **The HRRR analysis is 39 minutes early and is model output.** Forecast hour 0
  of the 04 UTC run is the closest analysis before a 04:39 report, not a
  measurement at the report, and a 3 km cell is not the parcel the storm ingested.
- **GLM flash counts are cloud-top detections.** A flash centroid is an
  energy-weighted cloud-top position rather than a ground strike, one flash that
  spans several counties counts once, and detection efficiency varies with viewing
  angle, cloud depth, and flash size.
- **The `grib` extra** installs with pip alone on Linux and on Windows through
  Python 3.13; macOS needs the ecCodes library from conda-forge or Homebrew first.
  See the [reader reference](https://docs.usdata.dev/reference/readers/).

The six sources revise differently, and the lockfile is what tells you which one
moved. NCEI republishes the current year's Storm Events archive each month under a
new creation date, so its asset id changes and `pull --force` is what moves to a
newer annual revision. SPC revises prior years in place under stable file names,
so the lockfile checksum is the only record that the bytes changed. GLM Level 2
files are republished when NOAA reprocesses them. The NEXRAD, MRMS, and HRRR
objects in the open-data buckets are normally written once, so a mismatch there
should be read as a replaced or removed object rather than as an expected
revision. A restore that finds different bytes exits 4 with the full list and
rewrites nothing; accept changes deliberately with
[`pull --update`](https://docs.usdata.dev/reference/manifests/#pull-refresh-and-restore),
or re-resolve everything with `pull --force`. A lockfile detects changed data and
does not archive it, so keep the manifest, the lockfile, and the cached bytes
together.

## Deeper dives

Each of these examines one link of this chain across more files than this
notebook pins:

- [GLM lightning flashes](https://usdata.dev/datasets/noaa/goes-glm/): a full hour
  of GOES-16 detections against a control box and the whole field of view.
- [MRMS rotation tracks](https://usdata.dev/datasets/noaa/mrms/): eleven
  two-minute grids, tie handling, and what the decode costs in memory.
- [HRRR environment](https://usdata.dev/datasets/noaa/hrrr/): the same two
  fields from the 20 UTC analysis, with maxima within 100 km and a map.
- [Derived radar products](https://usdata.dev/datasets/noaa/nexrad-level3/): the
  Level III mesocyclone, storm-track, and echo-top files from the same radar.
- [One year of SPC tornado reports](https://usdata.dev/datasets/noaa/spc-tornado-reports/):
  the whole 2024 file counted by rating.
- [Global model environment](https://usdata.dev/datasets/noaa/gfs/): the
  same fields from the coarse global analysis, 28.65 hours before the report.

## What was awkward

- A manifest can be priced now, but it still cannot be priced exactly.
  `pull --dry-run` reports `at least 84630235 bytes; size unknown for 1 asset(s)
  from spc`, which is honest and names the source, and the per-source line for
  SPC still reads `at least 0 bytes`. The real 230,094 bytes exist only after the
  download, because the SPC page publishes approximate sizes and the adapter
  records none, so the figure this README quotes had to come from the pull rather
  than from the plan.
- The derived Storm Events columns are pandas timestamps and asset times are
  `datetime` objects. Subtracting one from the other gives a `Timedelta` that
  prints as `0 days 00:39:00` where the notebook's other clocks print `0:39:00`,
  so `REPORT_UTC` is taken through `.to_pydatetime()` to keep one type flowing
  through the rest of the notebook. The provider page shows the column and its
  rule but says nothing about its dtype.
