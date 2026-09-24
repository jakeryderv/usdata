# CO-OPS observed currents

`noaa:coops-currents` is available since v0.24.0.
It fetches native six-minute observed current speed and direction for one
explicit station and bin from the anonymous
[CO-OPS Data API](https://api.tidesandcurrents.noaa.gov/api/prod/).

Require an ASCII alphanumeric string `station`, a positive integer `bin`, and
both timestamps. IDs include `cb0102` (Cape Henry) and `CFR1624` (a historical
survey station); preserve the published spelling. Unlike
[water levels](noaa-coops.md), currents need no vertical `datum`.
`units` is `metric` (default, **cm/s**) or `english` (**knots**).
Direction is delivered in degrees. Unknown parameters, geographic/text
selectors, and `variables` are rejected. Availability of a station, bin, and
time combination is checked when fetching.

The request fixes `time_zone=gmt` and `format=csv`. Offsets are normalized to
UTC; bounds are inclusive and must have zero seconds/microseconds. A bare end
date means 23:59 that day. The maximum interval is 28 days, conservatively
within NOAA's one-month limit. Longer windows must be split explicitly.

```sh
uv run usdata fetch noaa:coops-currents \
  --start 2025-05-06 --end 2025-05-06 \
  -p station=cb0102 -p bin=4 -p units=metric
```

## Bins, gaps, and units

A bin identifies a sampling cell, not a permanent depth. NOAA notes that
sensor depth and bin size can change between deployments. Some instruments
look sideways, with distance instead of depth in their bin metadata. Consult
the [Metadata API](https://api.tidesandcurrents.noaa.gov/mdapi/prod/) for the
station's bins and deployments and retain dated metadata with your analysis.
The adapter requires a bin even where NOAA offers a station default, so the
requested selection is explicit in its URL, asset identity, and provenance.
`bin=0` (all bins) is outside this adapter's scope.

Raw CSV retains NOAA's header spacing, blank measurements, and gaps. It has
`Date Time`, `Speed`, `Direction`, and `Bin`; it contains neither depth nor a
preliminary/verified quality field. Absence of a quality flag is not a claim
of verified data. The ordinary pandas CSV reader opens it; strip column names
locally if convenient. An empty response, malformed measurements, mismatched
bin, or out-of-window row fails before replacing the destination. Blank
measurements are preserved, not filled or counted as zero.

No interval selector is exposed. The API documentation mentions hourly
currents in one section but says only the native six-minute interval is
available in another. The dated probe below found `interval=h` ignored.
No resampling, vector averaging, predictions, automatic station discovery,
or detailed echo/correlation fields are included.

The [Cape Henry notebook](https://usdata.dev/datasets/noaa/coops-currents/)
plots one UTC day as an along-channel current, counts gaps and missing values,
gives dated bin/deployment context, and verifies its pinned CSV. Query responses
may be revised; a successful verify establishes equality at execution time.

## Source probe, 2026-09-22

Using the command above, Cape Henry bin 4 returned 239 observations from
00:02 to 23:56 UTC, with one missing six-minute timestamp at 19:32. There were
no blank measurements or duplicate timestamps. Speeds ranged from 1.6 to
85.8 cm/s. Repeating the query returned identical bytes; a request with
`interval=h` returned those same bytes. English-unit speeds matched the
metric values after conversion from knots, within rounding.

Current metadata reports bin 4 at 6.52 m and an active deployment beginning
2025-01-27, before the example day. This is dated context, not independent
verification of the historical depth. The example commits the exact metadata
responses with URLs and SHA256 hashes. Invalid bin 999 returned HTTP 400.
A short, unchanged response is retained as the
[test fixture](https://github.com/jakeryderv/usdata/blob/main/tests/fixtures/coops-currents.md).

## Metadata sources

- Cadence, units, bin selection, deployment caveat, and retrieval limit:
  [Data API documentation](https://api.tidesandcurrents.noaa.gov/api/prod/).
  The adapter's `MAX_INTERVAL` in `usdata.providers.noaa.coops` enforces the
  registry's `P28D` limit.
- Variables: the probed CSV header and NOAA's
  [response definitions](https://api.tidesandcurrents.noaa.gov/api/prod/responseHelp.html).
- Spatial selection and bin/deployment metadata:
  [Metadata API](https://api.tidesandcurrents.noaa.gov/mdapi/prod/).
- Direction terminology: NOAA's [glossary](https://tidesandcurrents.noaa.gov/glossary.html)
  defines current direction as the direction toward which water flows. The
  example plots the reported angle without calculating flood/ebb classifications.
- Terms: [CO-OPS disclaimer](https://tidesandcurrents.noaa.gov/disclaimers.html),
  which asks that NOAA National Ocean Service be acknowledged as the source.
  Citation uses the agency, product, and access form; no product-specific
  citation form is given there.
- Update frequency and latency are omitted: the cited API documentation does
  not state a publication cadence or lag distinct from the sampling interval.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/coops-currents.md#catalog-reference).
