# How did currents change at Cape Henry on 6 May 2025?

The [executed notebook](example.ipynb) plots one UTC day of observed current
speed and direction at Cape Henry LB 2CH (`cb0102`), bin 4. The
[manifest](dataset.yaml) names that exact selection, with metric speeds in
cm/s. Missing samples remain visible, and the final step restores the pinned
CSV byte-for-byte into a fresh cache.

CO-OPS currents support is available from source for the unreleased v0.24.0.
Follow the [source installation instructions](https://docs.usdata.dev/install/#source-installation)
and [examples setup](https://usdata.dev/examples/#run-examples), then open
`examples/coastal-currents/example.ipynb`.

The execution on 2026-09-22 returned 239 observations, with one missing
six-minute sample at 19:32 UTC, no blank measurements, and no duplicate
timestamps. Speeds ranged from **1.6 to 85.8 cm/s**. The plot shows the
observations without interpolating gaps or averaging circular directions.
The CSV has no verification-quality flag; missing flags do not imply verified
quality. This describes one station, bin, and day, not a navigation forecast.

NOAA's metadata retrieved on 2026-09-22 reports bin 4 at 6.52 m and a
downward-looking instrument, with the listed active deployment starting
2025-01-27. Exact metadata responses, source URLs, and checksums are kept in
the [dated metadata snapshot](https://github.com/jakeryderv/usdata/blob/main/examples/coastal-currents/metadata.json).
This is context from the current metadata service, not independent verification
of that depth on the historical day. The plot is labeled by bin, and does not
assume bin numbers always correspond to fixed depths.

See the [provider guide](https://docs.usdata.dev/providers/noaa-coops-currents/)
for access limits, units, and source references. Keep the manifest, resulting
lockfile, metadata snapshot, and cached bytes with the analysis. CO-OPS may
revise responses; this query-service example generates its lockfile when run,
and the restore check proves reproducibility at execution time.

## What was awkward

- The CSV carries a bin number but no depth; depth context needs dated station
  metadata, and even then historical applicability needs care.
- Metric speed means cm/s, not m/s. The CSV does not put units in its header.
- Six-minute records here fall at `:02`, `:08`, and so on; one is missing.
  The notebook verifies that grid before counting gaps and never fills them.
- Direction is circular, so the notebook uses unconnected points for angles.
- NOAA's hourly-interval documentation conflicts with the live service:
  `interval=h` returned the same six-minute data in the probe.
