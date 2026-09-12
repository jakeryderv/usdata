# Was 2024 warmer or wetter than normal?

Open the [executed notebook](example.ipynb) to compare twelve months of 2024
observations at Will Rogers World Airport against the 1991-2020 normals for the
same station, plot both anomaly series, and verify the manifest's locked inputs.
The calculated summary counts warmer-than-normal months and compares total
precipitation with the sum of the monthly normals. It describes this station
and year, not a climate trend or statistical significance.
See [examples setup](https://docs.usdata.dev/project/) to run it.

Requires usdata v0.11 or newer for `noaa:climate-normals`. The retained
[manifest](dataset.yaml) holds both sources: `noaa:gsom` with the 2024 calendar
year, and `noaa:climate-normals` with `period: monthly` and no dates, because
normals are 30-year averages rather than observations. The anomaly is the
observed value minus its normal.

The two `DATE` columns carry different labels: GSOM uses `YYYY-MM` and monthly
normals use `MM`, so the notebook reads both as text and relabels the normals
onto the observed months. NCEI's `units=metric` converts `MLY-PRCP-NORMAL` but
not `MLY-TAVG-NORMAL`, which arrives in degrees Fahrenheit; the notebook detects
that and converts it rather than subtracting mixed units.

Both sources are query-shaped URLs that the agencies revise, so a lockfile can
go stale. See [`--update` in the manifest reference](https://docs.usdata.dev/reference/manifests/#pull-refresh-and-restore)
for accepting new bytes for named entries, and the
[NOAA normals notes](https://docs.usdata.dev/providers/noaa-normals/) for
variable codes and units. Keep the manifest, lockfile, and cached bytes
together.
