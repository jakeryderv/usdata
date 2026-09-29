# 0049: GSOM long records come from NCEI's static station files, as their own dataset

Status: accepted. Date: 2026-09-28.

## Context

The El Niño snowfall study ([issue 390](https://github.com/jakeryderv/usdata/issues/390))
needs 77 winters of monthly snowfall at 315 USHCN stations. `noaa:gsom` reads
the Global Summary of the Month through NCEI's Access Data Service, which
builds each response on the server, 50 stations per request. On 2026-09-28 its
throughput swung between about 35 kB/s and 4 kB/s, and one 50-station,
77-year `SNOW` request sent nothing for more than three 120-second read
timeouts. One pull finished 1 of its 9 requests in 15 minutes. That is too slow
for a notebook cell or a weekly check, and it depends on the service's load.

NCEI also publishes every GSOM station as a static CSV at
`data/global-summary-of-the-month/access/<station>.csv`, which its GSOM
documentation names as where the data files are. A 407 kB file arrived in
0.7 s, and Pittsburgh's snowfall for five winter months matched the service's
metric output value for value. A file holds the station's whole record of every
element in metric units, with no server-side selection.

## Decision

The static files are a separate dataset, `noaa:gsom-station-files`, not a mode
of `noaa:gsom`. A dataset's capabilities are declared once in the registry and
checked against its adapter, and the two access routes differ in all three:
the service selects months, places, and elements, and the files select
nothing. A parameter that switched `noaa:gsom` between them would make its
declared capabilities false for one mode.

An asset is one station's whole file, `<station>.csv`, with `properties`
recording `units: metric`, which the file does not state. `stations` is the
only parameter, and a window, a box, variables, and text are refused. The
directory is too large to list, so listing makes no request and leaves size
unknown, and a station without a file fails at fetch with a 404. Each station is
its own pin, so NCEI's weekly rewrite of one station leaves the rest of a
lockfile valid.

## Alternatives

- **Smaller service requests** (fewer than 50 stations each). This is still
  the same service, it is untested whether small queries stall less, and the
  chunk size is shared with GHCN-Daily.
- **A `source` parameter on `noaa:gsom`.** Rejected above: one dataset, two
  capability sets.
- **Retry later.** The service's speed is not ours to fix, and a study that
  works only on a good night is not reproducible in practice.

## Consequences

Two datasets serve the same GSOM values. The registry says which to use when,
and the guide shows that they agree. A station file carries every element, so
pulling many stations downloads more than the one element a study may need.
The study's 315 USHCN stations are 199 MB, about 630 kB each, where `SNOW`
alone would be about 50 kB. They arrived in 49 seconds on 2026-09-28, against
more than 15 minutes for one failed pull through the service.
