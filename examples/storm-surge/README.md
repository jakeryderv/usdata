# How high was Hurricane Helene's storm surge at Cedar Key?

Open the [executed notebook](example.ipynb) to subtract CO-OPS tide predictions
from the observed water levels at Cedar Key, Florida, across Hurricane Helene's
landfall on 27 September 2024, find the peak of the non-tidal residual, and
time it against the HURDAT2 best track. The residual at one gauge is the
closest routine measurement of storm surge; it is not a regional surge height
or a return-period estimate. See [examples setup](https://docs.usdata.dev/project/) to run it.

Available from source for the unreleased v0.14.0, which adds
`noaa:coops-tide-predictions`. The retained [manifest](dataset.yaml) holds three
sources: observed six-minute water levels and six-minute tide predictions for
station 8727520 over the same three UTC days, both relative to mean lower low
water in meters, and the whole Atlantic HURDAT2 file, which takes no dates.

Observed and predicted rows share their timestamps when requested with the same
bounds and interval, so the notebook subtracts them directly. The datum cancels
in the subtraction; the residual includes wind setup, pressure effects, and any
wave setup the gauge resolves, which is why it is called a residual rather than
a surge. Best-track positions are six-hourly plus special landfall and peak
points, so the distance between the storm and the gauge at the moment of peak
residual is interpolated, not observed.

All three sources are revised upstream: NOAA re-verifies observations, updates
harmonic constituents behind predictions, and replaces the HURDAT2 file each
season, so a lockfile can go stale. See [`--update` in the manifest reference](https://docs.usdata.dev/reference/manifests/#pull-refresh-and-restore)
for accepting new bytes for named entries, and the
[tide-prediction notes](https://docs.usdata.dev/providers/noaa-coops-predictions/)
for intervals and limits. Keep the manifest, lockfile, and cached bytes together.
