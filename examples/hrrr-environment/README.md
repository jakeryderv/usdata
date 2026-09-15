# What did the HRRR analysis say about the storm environment over central Oklahoma at 20 UTC, and how far was the tornado report from the most favorable values?

Open the [executed notebook](example.ipynb) to read surface CAPE and 0-3 km
storm-relative helicity out of one HRRR analysis file, compare the values at the
grid point nearest an Oklahoma tornado report with the largest values within
100 km of it, and see both fields on one map. The answer measures where one
model run placed the most favorable environment relative to a point on the
ground, inside a single analysis hour. It does not measure the air the storm
ingested, it does not verify anything at the time of the report, and CAPE and
helicity are ingredients rather than a tornado detection. See
[examples setup](https://docs.usdata.dev/project/) to run it.

Available since v0.15.0, which adds `noaa:hrrr`. The retained
[manifest](dataset.yaml) holds one source: forecast hour 0 of the run
initialized at 20:00 UTC on 2024-05-06, which is the analysis, the model's own
estimate of the atmosphere at initialization rather than a projection forward
from it. `noaa:hrrr` offers temporal subsetting only, so the query chooses the
run and the hour and nothing else. The run downloaded as one object of
150,114,757 bytes, 150.1 MB, in 4.3 seconds at about 35 MB/s from the anonymous
`noaa-hrrr-bdp-pds` S3 bucket; decoding the selected messages took 1.3 seconds
and the whole notebook ran in 6.7 seconds.

Message selection is the part worth watching. The surface file holds 170 GRIB2
messages and `open()` refuses to guess, so the notebook first triggers the
reader's inventory, a 5,817 character `ValueError` listing every
`(shortName, typeOfLevel, level)` triple in the file, and then selects with
`select={"shortName": ["cape", "hlcy"], "typeOfLevel": ["surface",
"heightAboveGroundLayer"]}`. Two short names crossed with two level types match
four messages, not two, so the Dataset also carries 0-1 km helicity and 0-3 km
layer CAPE, and every variable is renamed to `shortName_typeOfLevel_level`
because the short names repeat. A value that matches nothing is dropped in
silence; only a select that matches no message at all raises.

The caveats that matter for the answer:

- The analysis is valid at 20:00 UTC on 2024-05-06 and the report begins at
  04:39 UTC on 2024-05-07, so it precedes the report by 8 hours 39 minutes.
  This is the afternoon environment over the region the storms later crossed,
  not the environment at the time of the report. The run valid then is
  `cycle: 4`, `forecast_hour: 0` on 2024-05-07, a separate 150 MB file.
- One grid point is a 3 km cell in a model. The nearest cell to the report is
  1.04 km away, which is close, but a storm ingests air over tens of
  kilometres, so the percentile rank of the report's cell within the radius is
  a fairer description than the single-cell number.
- The 100 km radius is an analysis choice made in the notebook, not something
  the package supplies. A larger radius reaches into a different air mass and
  moves the maxima.
- Report 1184052's coordinates and UTC start time are written into the notebook
  as constants, taken from the Storm Events archive as resolved by the
  [event context example](https://usdata.dev/examples/event-context/), so that
  this example downloads only the model file.
- HRRR longitudes are stored in the 0 to 360 convention on a Lambert conformal
  grid with two-dimensional `latitude` and `longitude` coordinates. The notebook
  unwraps them and measures geodesic distance with `pyproj` rather than
  differencing degrees.
- The `grib` extra installs with pip alone on Linux and on Windows through
  Python 3.13; macOS needs the ecCodes library from conda-forge or Homebrew
  first. See the [reader reference](https://docs.usdata.dev/reference/readers/)
  and the [NOAA access notes](https://docs.usdata.dev/providers/noaa-hrrr/) for
  cycles, forecast hours, file variants, and field selection keys.

The provider notes describe no revision cycle for archived HRRR runs, unlike the
NCEI archives used elsewhere in these examples, so a checksum mismatch here
should be read as a replaced or removed object rather than as an expected
revision. The lockfile pins the object name and its SHA-256 either way. Keep the
manifest, lockfile, and cached bytes together; public cloud retention is not a
promise.

## What was awkward

- `--dry-run` does not print the download size, although
  [the model output guide](https://docs.usdata.dev/guides/model-output/) says
  "Always dry-run first; the listing reports exact sizes" and the HRRR provider
  page frames it as the way to "check what a query will download before
  fetching". The command prints only the asset id and the S3 URL. The number
  exists at listing time, because the same object reports
  `size: 150114757` in provenance right after the download, so a student is
  told to check a figure the tool then withholds.
- The example README this notebook replaces said the 20 UTC run is "the hour of
  the Oklahoma Storm Events report used by the event context example". That
  report begins at 2024-05-07T04:39:00Z and the analysis is valid at
  2024-05-06T20:00:00Z, 8 hours 39 minutes earlier. The
  [GFS example README](https://usdata.dev/examples/gfs-environment/) has the
  same problem in the other direction: it calls its 00 UTC 2024-05-06 analysis
  "twenty hours before" the same report, when the gap is 28.65 hours. Both
  readings invite a student to treat a pre-convective analysis as concurrent
  with the event.
- A `select` value that matches no message is dropped silently. Only a select
  that matches nothing at all raises. The example in
  [the readers concept page](https://docs.usdata.dev/concepts/readers/) is
  itself an instance:
  `select={"shortName": ["cape", "hlcy"], "typeOfLevel": "surface"}` returns a
  Dataset containing `cape` alone, because HRRR carries no `hlcy` at
  `typeOfLevel: surface`, and nothing says so. A typo in a list of short names
  costs a field with no message at all.
- The only inventory of a GRIB2 file is the text of an exception. To print what
  the file holds, a notebook has to provoke a `ValueError` and read its 5,817
  character message, which arrives as one line containing duplicate triples and
  a dozen `unknown` short names from HRRR's local parameter tables. There is no
  method that returns the inventory as data.
- Variable names cannot be predicted before the first run.
  `cape_surface_0` and `hlcy_heightAboveGroundLayer_3000` follow from a rule
  stated in the concepts page, but the guide's shorter version of that rule,
  "Variables that share a `shortName` get the level appended to their names",
  omits the level type that is also appended. Writing the next line of analysis
  code means running the select once to see what came back.
- Units arrive as raw ecCodes strings, `J kg**-1` and `m**2 s**-2`. Every plot
  label and sentence has to translate them by hand, and there is no documented
  canonical form to translate to.
- Finding the grid point nearest a location is left entirely to the caller, and
  every model example in this repository solves it differently. The snippet this
  README replaces used `(cape.latitude - 35.47) ** 2 + ((cape.longitude % 360) -
  (-97.52 % 360)) ** 2`, which is a squared difference of degrees rather than a
  distance, is anisotropic away from the equator, and breaks across the
  antimeridian. The GFS README uses a different one-dimensional variant. A
  documented nearest-point pattern, or a helper, would stop each example
  inventing its own.
- The projection arrives as raw ecCodes keys on `Dataset.attrs`
  (`LaDInDegrees`, `Latin1InDegrees`, `DxInMetres`, `shapeOfTheEarth`) with no
  CRS object and no documented mapping to a pyproj or CF projection, so any
  work in projected coordinates starts by reverse-engineering those keys.
- Refreshing one notebook needs `just run-notebooks --notebook
  examples/hrrr-environment/example.ipynb`, a repository-relative path. A slug
  is rejected with "unknown example notebooks". `examples/README.md` documents
  `just run-notebooks` and `--write` but not `--notebook`; that flag appears
  only in `docs/testing.md`, which is a contributor page excluded from the site.
- The retrieval URL is `item.provenance.source_url` while the asset's is
  `item.asset.href`. Two names for the same idea on two objects that are
  usually used in the same breath cost a round trip through an `AttributeError`.
