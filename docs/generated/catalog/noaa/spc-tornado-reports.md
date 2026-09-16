# SPC tornado database

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:spc-tornado-reports` · **Released** · Included since usdata 0.15.

SPC Tornado Reports.

## At a glance

- Files: CSV
- Selection: Whole annual, half-decade, or decade files; filter rows locally after downloading
- Required inputs: Both dates (selects the files covering those years)
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [spc tornadoes](https://usdata.dev/examples/spc-tornadoes/), [severe weather case study](https://usdata.dev/examples/severe-weather-case-study/)

## Parameters

This dataset accepts no provider-specific parameters.

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `om` | — | Tornado number within the year, repeated across a tornado's segments |
| `date` | — | Touchdown date |
| `time` | — | Touchdown time |
| `tz` | — | Time-zone code: 3 is Central Standard Time, 9 is GMT, ? is unknown |
| `st` | — | Two-letter state |
| `stf` | — | State FIPS code |
| `mag` | — | F scale through January 2007 and EF scale afterwards; -9 is unknown |
| `inj` | count | Injuries |
| `fat` | count | Fatalities |
| `loss` | — | Property loss: a 0 to 9 category before 1996, millions of dollars from 1996 |
| `closs` | millions of dollars | Crop loss |
| `slat` | degrees_north | Start latitude |
| `slon` | degrees_east | Start longitude |
| `elat` | degrees_north | End latitude |
| `elon` | degrees_east | End longitude |
| `len` | miles | Path length |
| `wid` | yards | Path width |
| `sg` | — | Segment code: 1 a whole track, 2 a state segment, -9 extra county codes |

## Usage and limitations

[Usage guide](../../../providers/noaa-spc-tornado.md).

## Catalog reference

- Availability: since 0.15
- Domain: Severe weather
- Spatial resolution: One row per tornado or per state and county segment, with start and end coordinates
- Temporal resolution: One row per tornado, timestamped in Central Standard Time
- Updates: Files are revised in place as NWS Storm Data is finalized; the page shows an update date per file
- Terms of use: <https://www.weather.gov/disclaimer>
- Citation: NOAA/NWS Storm Prediction Center, Severe Weather Database tornado files, accessed via usdata
- Catalog date range: 1950-01-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.spc.noaa.gov/wcm/#data)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.spc:SpcTornadoReports`

[All NOAA datasets](../noaa.md).
