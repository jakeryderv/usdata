# Where was the strongest mid-level rotation in each two-minute grid, and did it move toward the reported tornado?

Open the [executed notebook](example.ipynb) to pull eleven MRMS mid-level
rotation grids, 04:30 to 04:50 UTC on 2024-05-07, locate the strongest value in
each one inside two stated boxes around Oklahoma Storm Events tornado report
1184052, and measure how far each peak sat from the reported path start. What
this measures is where radar-derived azimuthal shear maxima were in the 3 to
6 km layer, in units of 0.001 s⁻¹. It is not a tornado detection, not a
storm-motion product, and not a statement about the low-level circulation that
a tornado report describes. See [examples setup](https://usdata.dev/examples/#run-examples)
to run it.

Available since v0.15.0, which adds `noaa:mrms` and the GRIB2 reader. The
retained [manifest](dataset.yaml) holds one source: the product
`RotationTrackML30min_00.50` over an inclusive UTC window of 04:30 to 04:50,
which selects the eleven two-minute files stamped in that range. MRMS rejects a
location or bounding box because each file is a whole CONUS grid the server
cannot crop, so every spatial narrowing happens locally after download. The
eleven files are 177 to 192 kB each, 2.03 MB in total, and each one decodes to a
7,000 × 14,000 grid of 0.39 GB. One open took peak resident memory from 0.14 to
1.34 GB, and the high-water mark across all eleven sequential opens reached
5.28 GB even though each grid is released before the next is opened, so allow
several gigabytes of headroom.

Every value is already a maximum over the thirty minutes before the file stamp,
so consecutive grids overlap heavily and a peak marks where the strongest shear
occurred at some point in that half hour, not where rotation is at the stamp.
That is why the peak position repeats exactly for several grids and then jumps
when an older maximum ages out of the window; the positions are a sequence of
accumulation maxima, not a storm track. The CONUS maximum in the first grid is
on the Pacific coast, 30 (0.001 s⁻¹) at 49.242° N, 124.188° W, which is why the
notebook works inside a ±1.0° search box and a ±0.25° storm box centred on the
report instead of taking a grid-wide maximum. Those boxes are an analysis choice
here, not a storm identification: a maximum inside one is not proof that it
belongs to the reported storm. Azimuthal shear also depends on radar range and
viewing angle, and high mid-level values are common in supercells that produce
no tornado.

The report's position (35.378° N, 97.543° W) and time (22:39 CST on May 6,
04:39 UTC on May 7) are constants in the notebook, taken from
[NCEI event 1184052](https://www.ncei.noaa.gov/stormevents/eventdetails.jsp?id=1184052).
The [tornado classification example](https://usdata.dev/examples/tornado-classification/)
pulls the Storm Events archive itself and converts the local time with the
source's own timezone column.

Files in the `noaa-mrms-pds` bucket are published once and are not normally
revised, but the lockfile is what tells you if that changes: a restore whose
bytes no longer match exits 4 and rewrites nothing. See
[`--update` in the manifest reference](https://docs.usdata.dev/reference/manifests/#pull-refresh-and-restore)
for accepting new bytes deliberately, and the
[MRMS notes](https://docs.usdata.dev/providers/noaa-mrms/) for the product list,
the one-day query limit, and the archive start of 2020-10-14. A lockfile detects
changed data and does not archive it, so keep the manifest, lockfile, and cached
bytes together.

## What was awkward

- `just run-notebooks --notebook mrms-rotation --write` fails with `unknown
  example notebooks: /repo/mrms-rotation`. The flag wants a path
  (`examples/mrms-rotation/example.ipynb`); the message neither says so nor
  shows an accepted form, and `examples/README.md` documents the command only
  without the flag.
- The [MRMS notes](https://docs.usdata.dev/providers/noaa-mrms/) and the
  previous version of this README both say to mask the `-999` no-coverage and
  `-99` no-data sentinels before taking statistics. These eleven grids contain
  no negative values and no NaN at all: 97.8 million of 98 million points are
  exactly 0.0, so no coverage and zero shear are indistinguishable, and a mask
  written from the documentation does nothing. Nothing states which products
  actually carry the sentinels.
- The decoded variable is named `RotationTrackML30min`, while the manifest must
  say `RotationTrackML30min_00.50`. You cannot index the returned Dataset with
  the product string you asked for; you have to unpack `(name,) =
  grid.data_vars` to find out what it is called.
- The decoded variable's `units` attribute is the literal string `unknown`. The
  units (0.001 s⁻¹) exist only in a table on the provider page, so a number read
  out of this file carries no units anywhere in the package.
- Nothing in the asset, the query, or the registry entry says the value is a
  trailing thirty-minute maximum. `asset.time` is `start == end == 04:30:00`,
  a zero-length range, which reads like an instantaneous observation and is
  actually the end of a half-hour accumulation. That one fact changes the whole
  interpretation and lives only in provider prose.
- There is no way to ask how large a decode will be. `--dry-run` reports the
  download size, about 180 kB per file, which is 2,000 times smaller than the
  0.39 GB array it becomes. Worse, peak resident memory over eleven sequential
  opens reached 5.28 GB although each grid was deleted and garbage-collected
  before the next open, roughly four times the 1.34 GB a single open costs; no
  documentation warns that repeated opens accumulate like that.
- Locating a maximum means writing the box slice yourself in the file's own
  frame: latitudes descend, so the slice runs north to south, and longitudes run
  0 to 360, so a negative longitude needs 360 added. Both conventions are prose
  in the reader docs. Getting either wrong silently returns a `(0, 0)`
  selection, and the failure only surfaces later as `zero-size array to
  reduction operation maximum`.
- Values arrive quantized to whole units of 0.001 s⁻¹, so up to twelve points
  tied at a box maximum in this window. `argmax` would have chosen one of them
  by array order and produced a confident position that is an artifact of array
  layout. The notebook reports the tie count and averages the tied positions
  instead. Nothing in the docs mentions the quantization.
- `usdata info noaa:mrms` prints `subsetting: temporal_subset, variable_subset`
  and `extent: (-130.0, 20.0, -60.0, 55.0)` for a dataset that rejects both a
  bbox and variables, and every asset comes back with `bbox: None` although all
  the files share one known CONUS grid. The extent invites exactly the manifest
  that the adapter then refuses; the refusal message is clear, the metadata that
  leads you there is not. `usdata info` also cannot list the twenty allowed
  products, saying "see the dataset guide"; a wrong product is only caught at
  fetch, though that error does then list them all.
- Answering a question about a report means supplying the report yourself. To
  keep this example at 2 MB, the report's coordinates and UTC time are constants
  pasted in from a separate Storm Events fetch, so those two numbers are not
  reproducible from this manifest. The alternative is pulling the whole annual
  archive, which is many times larger than the analysis.
