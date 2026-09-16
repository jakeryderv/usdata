# For one Oklahoma tornado, do the two report archives agree on when and where it was, and what did radar, lightning, and the model analysis show at that place and time?

Open the [executed notebook](example.ipynb) to take one tornado report out of the
2024 Storm Events archive, confirm it against the Storm Prediction Center's own
2024 tornado file, and then ask the nearest KTLX Level II volume, five MRMS
mid-level rotation grids, twenty minutes of GOES-16 lightning, and the last HRRR
analysis before the report what each of them recorded at that time and place. The
answer measures agreement between two publication paths for one storm survey, and
what four remote-sensing and model products held within 25 km of the reported
path start. It does not detect a tornado in any of those products, it does not
establish that any of these quantities precede tornadoes in general, and it is
one case. See [examples setup](https://usdata.dev/examples/) to run it.

Available from source for the unreleased v0.17.0, which adds the named manifest
sources this example is built on, `FetchedAsset.inspect()`, the strict GRIB2
`select`, registry-filled units, and `usdata cite`. The retained
[manifest](dataset.yaml) holds six named sources, and the notebook addresses each
one through `result.by_source["..."]`:

| Source | Dataset | What it pins | Assets | Bytes |
|---|---|---|---|---|
| `reports` | `noaa:storm-events` | The whole 2024 annual details archive, selected by a 2024-05-06 window | 1 | 12,693,243 |
| `spc` | `noaa:spc-tornado-reports` | The whole `2024_torn.csv` file | 1 | 230,094 |
| `radar` | `noaa:nexrad-level2` | Every KTLX volume scan between 04:34 and 04:46 UTC on 2024-05-07 | 2 | 39,708,043 |
| `rotation` | `noaa:mrms` | `RotationTrackML30min_00.50` grids stamped 04:34 to 04:42 UTC | 5 | 926,976 |
| `lightning` | `noaa:goes-glm` | GOES-16 GLM files starting 04:29:00 to 04:48:59 UTC | 60 | 29,536,150 |
| `environment` | `noaa:hrrr` | Forecast hour 0 of the 04 UTC run, surface file | 1 | 133,253,838 |

That is **216,348,344 bytes, 216.3 MB, across 70 assets**. The live pull took
20.2 seconds and the whole notebook ran in 41 seconds. Nothing is subsetted on
the server: Storm Events and SPC arrive as whole annual tables, MRMS and GLM as
whole CONUS and full-disk files, HRRR as a whole 3 km CONUS grid. Every spatial
and variable narrowing happens locally.

`usdata fetch` with `--dry-run` lists what a query will download before anything
is pulled, one source at a time:

```sh
usdata fetch noaa:storm-events --start 2024-05-06 --end 2024-05-06 --dry-run
usdata fetch noaa:spc-tornado-reports --start 2024-01-01 --end 2024-12-31 --dry-run
usdata fetch noaa:nexrad-level2 --start 2024-05-07T04:34:00Z --end 2024-05-07T04:46:00Z \
    -p site=KTLX --dry-run
usdata fetch noaa:mrms --start 2024-05-07T04:34:00Z --end 2024-05-07T04:42:00Z \
    -p product=RotationTrackML30min_00.50 --dry-run
usdata fetch noaa:goes-glm --start 2024-05-07T04:29:00Z --end 2024-05-07T04:48:59Z \
    -p satellite=16 --dry-run
usdata fetch noaa:hrrr --start 2024-05-07T04:00:00Z --end 2024-05-07T04:00:00Z \
    -p cycle=4 -p forecast_hour=0 -p file=sfc --dry-run
```

Each prints one line per asset with its size and then a total, except the SPC
file, which reports `1 asset(s) matched, 0 bytes; size unknown for 1` because the
SPC page gives only approximate sizes.

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
  is UTC. The notebook converts both with an explicit fixed offset and checks the
  timezone column before it does.
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

- [GLM lightning flashes](https://usdata.dev/examples/glm-flashes/): a full hour
  of GOES-16 detections against a control box and the whole field of view.
- [MRMS rotation tracks](https://usdata.dev/examples/mrms-rotation/): eleven
  two-minute grids, tie handling, and what the decode costs in memory.
- [HRRR environment](https://usdata.dev/examples/hrrr-environment/): the same two
  fields from the 20 UTC analysis, with maxima within 100 km and a map.
- [Derived radar products](https://usdata.dev/examples/radar-products/): the
  Level III mesocyclone, storm-track, and echo-top files from the same radar.
- [One year of SPC tornado reports](https://usdata.dev/examples/spc-tornadoes/):
  the whole 2024 file counted by rating.
- [Global model environment](https://usdata.dev/examples/gfs-environment/): the
  same fields from the coarse global analysis, 28.65 hours before the report.

## What was awkward

- There is no way to price a manifest before pulling it. `usdata pull` has no
  `--dry-run`, so the only way to learn that this manifest weighs 216.3 MB was to
  retype all six sources as `usdata fetch` flag sets and add the totals by hand.
  The YAML already says every one of those queries; the CLI cannot read it.
- The one dry run that mattered most for the budget came back empty. The SPC
  source prints `1 asset(s) matched, 0 bytes; size unknown for 1`, because the SPC
  page publishes approximate sizes and the adapter records none. The real figure,
  230,094 bytes, exists only after the download. A total assembled from dry runs
  can therefore understate what a pull will fetch, and the summary line reads like
  a zero-byte result rather than a missing measurement.
- `usdata cite` exists only as a command. `cite_dataset` and `cite_lockfile` are
  exported from the package root and appear in no page under `docs/`, including
  the Python API reference, and nothing documents a way to render a `Citation` as
  text or BibTeX from Python. A notebook that wants both renderings has to shell
  out to the CLI.
- Shelling out has no supported spelling either. `python -m usdata` fails with
  `No module named usdata.__main__`, so the last cell has to guess the console
  script's location from `Path(sys.executable).with_name("usdata")`. Inside the
  notebook runner's kernel that is the only thing that reliably works.
- Four of the six citations contain a literal `[date]` placeholder, for example
  `NEXRAD on AWS was accessed on [date] from ...`. The real retrieval date is
  printed two lines below in the text rendering, but in BibTeX the placeholder
  lands inside `howpublished` and the date inside `note`, so anyone who pastes the
  entry into a bibliography publishes the word `[date]`.
- `inspect()` is documented in prose but not in a form you can type. The readers
  page says a GRIB2 summary reports each message's `shortName`, `typeOfLevel`,
  `level`, `step`, `units`, and shape, which are the ecCodes spellings; the object
  actually exposes `summary.grib2.messages[i].short_name` and `.type_of_level`.
  The attribute path itself appears nowhere, and `FetchedAsset.inspect`,
  `inspect_asset`, and `inspect_path` are all missing from the Python API
  reference, whose `FetchedAsset` member list stops at `open`. Finding the field
  names meant printing the dataclass repr.
- GRIB2 variable names still depend on what else the select matched. Asking for
  `{"shortName": ["cape", "hlcy"], "typeOfLevel": ["surface",
  "heightAboveGroundLayer"], "level": [0, 3000]}` returns `cape_surface_0`,
  `cape_heightAboveGroundLayer_0`, and a bare `hlcy`, because the suffix is added
  only to the short names that collided. The notebook ends up issuing two narrow
  `open()` calls, each matching exactly one message, purely so the variable names
  are predictable.
- `by_source` always hands back a list, so a source that can only ever resolve to
  one file is unpacked with `(item,) = result.by_source["reports"]` four times in
  this notebook. Within a source, the documented order is "the order the adapter
  listed that source's assets", which is not promised to be chronological, so
  anything that wants the earliest or latest asset sorts on
  `item.asset.time.start` defensively.
- Converting a Storm Events timestamp is still hand work. `CZ_TIMEZONE` is the
  string `CST-6`, which no Python timezone accepts, so every example that touches
  this dataset builds `timezone(timedelta(hours=-6))` from the suffix itself and
  checks the string first. Three notebooks in this repository now carry their own
  copy of that conversion, and the provider page describes the column without
  offering a rule for turning it into an offset.
- The registry points at two different kinds of page for the same kind of example.
  `usdata info noaa:hrrr`, `noaa:mrms`, and `noaa:goes-glm` list a `README.md`
  under `examples:` although all three examples now ship executed notebooks, while
  `noaa:storm-events` and `noaa:nexrad-level2` list `example.ipynb`. A student
  following `usdata info` lands on a page or on a notebook depending on which
  dataset they asked about.
- Iterating on this example re-downloads it every time. `just run-notebooks` sets
  `USDATA_CACHE_DIR` to a fresh directory per run, which is the right default for
  checking that a notebook works from nothing, but it means each `--write` pulls
  216 MB again and there is no flag or documented override to point one run at a
  warm cache.
