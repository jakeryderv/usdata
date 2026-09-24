# CO-OPS tide predictions

Available since v0.14.0 as `noaa:coops-tide-predictions`.
The adapter fetches astronomical tide predictions for one explicit station from
the same anonymous CO-OPS Data API as the
[observed water levels](noaa-coops.md), with the same station, datum, units,
and timestamp rules, so the two series align row for row when requested on the
same interval. Subtracting the prediction from the observation isolates the
non-tidal residual, which during a tropical cyclone is dominated by storm surge.

Require a seven-digit string `station`, an explicit uppercase `datum`, and both
timestamps. `units` is `metric` (default, meters) or `english` (feet). Supported
datum codes follow the [Data API documentation](https://api.tidesandcurrents.noaa.gov/api/dev/):
CRD, IGLD, LWD, MHHW, MHW, MTL, MSL, MLW, MLLW, NAVD, and STND; availability
depends on the station. `interval` selects the series: `6` (default) or another
minute step from 1, 5, 10, 15, 30, and 60; `h` for hourly; or `hilo` for high
and low tides only, which adds a `Type` column of `H` or `L`. Subordinate
stations serve only `hilo`; the service rejects other intervals there during
fetching. Unknown parameters, geographic/text selectors, and `variables` are
rejected.

Offsets are normalized to UTC and the API request fixes `time_zone=gmt`. Bounds
are inclusive, must have zero seconds/microseconds, and span at most 366 days
on any interval, within NOAA's one-year limit for predictions. A year of
six-minute predictions is about 87,600 rows. A date alone as the end means 23:59 on that day.
The adapter constructs one stable CSV request; it checks the response on fetch.

```sh
uv run usdata fetch noaa:coops-tide-predictions \
  --start 2024-05-06T00:00Z --end 2024-05-07T00:00Z \
  -p station=8518750 -p datum=MLLW -p interval=hilo
```

The raw CSV retains NOAA's header spacing. Use the ordinary CSV reader and
rename columns locally if desired; station, datum, units, interval, and
timezone remain explicit in the provenance source URL. Predictions are computed
from harmonic constituents, not observed, so they carry no quality flags and
never contain gaps. NOAA occasionally revises a station's constituents, after
which the same request returns different bytes. The
[storm-surge notebook](https://usdata.dev/studies/storm-surge/) subtracts
predictions from observations during Hurricane Helene.

See the [service research notes](noaa-services.md#co-ops-tide-predictions) for dated upstream probes.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Resolution, updates, and the longest window: the [Data API
  documentation](https://api.tidesandcurrents.noaa.gov/api/prod/), which lists the
  prediction intervals and limits non-`hilo` intervals to one year; the adapter's
  `MAX_PREDICTION_INTERVAL` in `usdata.providers.noaa.coops` sets the declared 366 days.
- Variables: the CSV header this adapter requests, including the `Type` column that only
  `hilo` returns.
- Terms: the [CO-OPS disclaimer](https://tidesandcurrents.noaa.gov/disclaimers.html).
- Citation: CO-OPS publishes no citation form, so the entry uses the agency, product,
  and access form.
- Latency is empty: predictions are computed on request, so no lag applies.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/coops-tide-predictions.md#catalog-reference).
