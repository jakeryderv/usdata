# Did lightning near the storm pick up before the Oklahoma City tornado report?

Open the [executed notebook](example.ipynb) to count GOES-16 Geostationary
Lightning Mapper flashes minute by minute inside a two-degree box around
Oklahoma Storm Events tornado report 1184052 (22:39 local standard time on
6 May 2024, 04:39 UTC on 7 May) over the sixty minutes that end at the report,
and to set that series against a same-size box ten degrees of longitude east
and against every flash the satellite recorded anywhere in its field of view
during the same hour. The answer measures how many flashes GLM detected per
minute inside a fixed square of latitude and longitude. It does not measure
storm intensity, it does not outline a storm, and it does not establish how
often a rising or falling flash rate precedes a tornado report.

Available since v0.15.0, which adds `noaa:goes-glm`. The
[manifest](dataset.yaml) requests GOES-16 GLM files whose start times fall
between 03:40:00 and 04:39:59 UTC on 2024-05-07. GLM writes one file every 20
seconds, so the hour is 180 files, about 90 MB on this active night; the same
query on the quiet afternoon of 2024-05-06 returns 59 MB. Each file is the whole
detection table for its 20 seconds over the satellite's entire field of view,
and the service cannot crop it, so every spatial narrowing happens locally after
download. See [examples setup](https://usdata.dev/examples/) to run it, and the
[NOAA access notes](https://docs.usdata.dev/providers/noaa-glm/) for the file
layout, the one-day query limit, and the flash, group, and event tables.

Until this notebook the manifest pinned 20:00 to 20:59 UTC on 2024-05-06 and
called it the hour around this report. That hour ends 8 hours 39 minutes before
the report begins, and it holds no flashes at all inside the two-degree box the
example itself described: 46,474 flashes in the field of view, none near
Oklahoma City. The manifest now covers the hour ending at the report.

What to keep in mind when reading the result. A flash centroid is an
energy-weighted cloud-top position, not a ground strike, and one flash spanning
several counties counts once. GLM's detection efficiency varies with viewing
angle, cloud depth, flash size, and background scene, which is why the notebook
also reports the whole field of view as a check on the instrument rather than
the storm. The box is fixed around one reported point: it does not move with the
storm, and it contains the other wind and hail reports from that evening as
well. The report time is a minute-resolution local-standard-time entry converted
at a fixed UTC-6 offset, taken as given here from the
[event context](https://usdata.dev/examples/event-context/) and
[tornado classification](https://usdata.dev/examples/tornado-classification/)
examples, which derive it from the Storm Events archive. A flash's first
constituent event can precede the nominal start of the file it was written to,
so the series is binned on decoded times, and the final minute of the window can
miss flashes whose first event fell in its last fraction of a second.

GLM Level 2 files are republished when NOAA reprocesses them. A locked restore
downloads each pinned URL and fails with a checksum mismatch when the bytes have
changed; accept the new bytes for named entries with
[`pull --update`](https://docs.usdata.dev/reference/manifests/#pull-refresh-and-restore),
or re-resolve the whole manifest with `pull --force`, then rerun the notebook.
A lockfile detects changed data, it does not archive it, so keep the manifest,
the lockfile, and the cached bytes together.

## What was awkward

- The manifest did not contain the case it advertised. `dataset.yaml` pinned
  2024-05-06T20:00:00Z to 20:59:59Z while the README, and `examples/catalog.json`,
  described it as the hour around Storm Events report 1184052, which begins at
  2024-05-07T04:39:00Z. Pulling the old hour and applying the README's own box
  gives 0 flashes of 46,474, so the documented per-minute snippet printed an
  empty series and nothing in the repository noticed.
- The documented way to get flashes into pandas raises. Both
  `docs/providers/noaa-glm.md` and this README used
  `detections[columns].reset_coords(drop=True).to_dataframe()` and then filtered
  on `flashes.flash_lat`. The flash latitude, longitude, and first-event time are
  xarray coordinates, so `drop=True` deletes exactly the three columns the next
  line needs, and the snippet ends in
  `AttributeError: 'DataFrame' object has no attribute 'flash_lat'`. The working
  spelling is `detections[columns].reset_coords()[columns].to_dataframe()`. The
  tornado classification notebook avoids the documented form entirely by reading
  `detections.flash_lat.values` off the Dataset, so nothing in the repository
  exercises what the docs tell a new user to type.
- Nothing in the provider notes says which GLM variables arrive as coordinates.
  The page explains the event, group, and flash tables and their parent-id links,
  but not that positions, times, and ids come back as coordinates while energy,
  area, and quality flags come back as data variables. That distinction is the
  whole cause of the bug above, and finding it took printing `sorted(ds.coords)`.
- There is no way to learn what a pull will weigh before running it.
  `usdata info noaa:goes-glm` reports coverage and parameters but no size, and
  `usdata pull` has no dry run, so the only way to find out that this hour is
  90 MB and the previously pinned hour is 59 MB was to download both.
- `usdata pull` prints one tab-separated line per asset. On a 180-file manifest
  that is 180 lines before the single summary line, and `--no-progress` does not
  suppress them: it still emits 181 lines. Its help text is also confusing,
  showing `--no-progress --no-no-progress` with `[default: no-no-progress]`.
- Combining files is left to every caller. The reader returns one dataset per
  20-second file and the docs say concatenation is the caller's job, so this
  notebook writes the same decode-and-concatenate loop that the tornado
  classification example writes in a different shape. A documented recipe, or a
  helper that concatenates a source's assets into one table, would stop each new
  user inventing it.
- `PullResult.fetched` has no documented ordering, so anything that reports a
  first or last file has to sort by `item.asset.time.start` first and hope that
  is the intended key.
- `just run-notebooks --notebook glm-flashes` is rejected. The flag wants the
  repository-relative path `examples/glm-flashes/example.ipynb`, and the error
  reads `unknown example notebooks: /abs/path/to/repo/glm-flashes`, which points
  at a path that was never typed. `examples/README.md` documents
  `just run-notebooks` without showing `--notebook` at all.
- The "examples guide" link that ten example READMEs point at,
  `https://usdata.dev/examples/#run-examples`, matches no page under `docs/` and no entry
  in the mkdocs nav. `mkdocs build --strict` only validates local links, so
  `just check` cannot see it, and a student following it from a sibling example
  lands nowhere.
