# How did central Plains infrared cloud patterns change over fifteen minutes?

The [executed notebook](example.ipynb) compares GOES-16 channel-13 mesoscale
sector M1 scenes from **22:00 to 22:15 UTC on 6 May 2024**, with the end
excluded. The [manifest](dataset.yaml) selects whole files; the analysis crops
a fixed **34–38°N, 100–96°W** region locally after checking every scene's
projection, coordinates, and reported footprint. It does not track an individual
storm or infer tornado intensity.

Mesoscale support is **Unreleased**; available from source for v0.25.0 using the
[examples setup](https://usdata.dev/examples/#run-examples). Open
`examples/goes-mesoscale/example.ipynb`. The existing example environment supplies
NetCDF reading, plotting, and pyproj for this notebook's geographic mask;
there is no new SDK dependency.

The execution on 2026-09-22 restored **15 scenes totaling 4,925,644 bytes**,
with one scan in each minute and no duplicate starts. Actual start intervals
were **57.1–62.9 seconds**, not an exact sixty-second grid. M1's footprint was
unchanged in this window. Every scan had 23,968 finite pixels with `DQF == 0`
inside the analysis region; none were excluded there.

The region's 10th-percentile brightness temperature fell from **220.09 K to
218.79 K**, while its fraction of accepted pixels below the illustrative
**235 K** threshold rose from **16.84% to 18.69%**. The three displayed frames
use the same color scale. These are pixel summaries, not area-weighted
statistics; cloud motion and growth can both change them. Channel-13 brightness
temperature is not surface air temperature, and ellipsoid-based cloud positions
have parallax uncertainty.

The archive-backed example commits `dataset.lock.json` and joins the weekly
empty-cache restore checks. The notebook also restores all fifteen scenes into
a second empty cache and compares their bytes. Preserve the manifest, lockfile,
and cached NetCDF files together. Exact source URLs, retrieval times, sizes,
and SHA-256 checksums are recorded in the notebook and lockfile. Re-pinning is
an explicit reviewed operation, never part of notebook execution.

See the [provider guide](https://docs.usdata.dev/providers/noaa-goes/),
[NOAA product reference](https://www.ncei.noaa.gov/products/goes-terrestrial-weather-abi-glm),
and [scan-mode documentation](https://goes-r.noaa.gov/users/abiScanModeInfo.html).

## What was awkward

- M1 and M2 share a bucket prefix. Choosing a product alone cannot select one
  sector, and a sector name does not tell you where it was pointed historically.
- Start seconds shift around the minute. Missing minute bins and actual time
  differences are reported separately; the analysis does not fill gaps.
- Fixed pixel indices are comparable only after checking that the sector did
  not move. The notebook stops if its coordinates or projection change.
- The geographic crop belongs to the analysis and needs projection handling;
  the archive still downloads complete scenes. White margins in the frame plots
  lie outside the crop, not necessarily in missing source data.
- A cold-cloud threshold describes a chosen subset of infrared pixels. It
  cannot by itself separate storm growth, movement, and changing coverage.
