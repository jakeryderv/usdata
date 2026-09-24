# How warm was Oklahoma City on 6 May 2024 compared with its hourly normals?

Open the [executed notebook](hourly-anomalies.ipynb) to compare one day's routine
temperature reports at Will Rogers World Airport with 1991–2020 hourly normals.
It plots the observed temperatures and their departures, reports missing and
unmatched values, and restores the two pinned files into an empty cache.

Hourly normals support is available in usdata v0.23.0 and later. Follow the
[examples setup](https://usdata.dev/studies/#run), then open
`examples/studies/hourly-anomalies/hourly-anomalies.ipynb`. The [manifest](dataset.yaml) names
LCD observations (`72353013967`) and normals (`USW00013967`) for the same airport.
Both request metric temperatures.

The observations are labeled in local standard time, as are the normals.
At this airport that is CST (UTC−6), including in May; using daylight-saving
civil time would shift the comparison by an hour. Routine `FM-15` reports
occur at `:52`, so the notebook matches them to the nearest hourly normal
within ten minutes. It preserves the actual report times and reports the
offsets. This approximation compares individual readings with hourly means;
it does not turn the readings into observed hourly averages.

The execution on 2026-09-21 found 24 usable pairs, with no invalid or unmatched
values. All 24 observations were warmer than their matched normals; their
mean departure was **2.88 C**. The largest was **7.5 C at 21:52 CST**, compared
with the 22:00 normal eight minutes later. The remaining 36 LCD rows were
other report types and were excluded explicitly.

The normals request includes May 7 because the final May 6 report matches
the next midnight. Their labels omit the year, and February 29 has no values.
See the [NOAA normals guide](https://docs.usdata.dev/providers/noaa-normals/)
for the calendar-window rules, units, and source documentation.

The comparison describes one station and day, not statistical rarity or a
climate trend. NCEI can revise both query responses. Keep the manifest,
lockfile, and cached bytes together; the notebook's fresh-cache restore proves
byte-for-byte reproducibility at execution time, not perpetual upstream availability.

## What was awkward

- The same airport has different station identifiers in the two products.
- Local standard time must not be interpreted as daylight-saving civil time,
  and normals have neither a year nor February 29 values.
- Observations and normals are eight minutes apart, requiring an explicit
  tolerance and the next day's midnight normal for the final observation.
- LCD mixes routine, special, synoptic, and summary reports. Quality suffixes
  can make a temperature nonnumeric; the notebook counts those values instead
  of silently removing the suffixes.
