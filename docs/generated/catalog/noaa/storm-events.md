# Storm Events details

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:storm-events` · **Released** · Included since usdata 0.8.

Storm Events Database.

## At a glance

- Files: gzip CSV
- Selection: Whole annual archives; filter rows locally after downloading
- Required inputs: Both dates (selects the containing years)
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [storm events](https://usdata.dev/examples/storm-events/), [event context](https://usdata.dev/examples/event-context/), [tornado classification](https://usdata.dev/examples/tornado-classification/)

## Parameters

This dataset accepts no provider-specific parameters.

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `EVENT_ID` | — | Identifier of one event record |
| `EPISODE_ID` | — | Identifier grouping the events of one storm episode |
| `CZ_TYPE` | — | County (C), forecast zone (Z), or marine (M) record |
| `CZ_FIPS` | — | County or zone code; not always a county FIPS code |
| `CZ_TIMEZONE` | — | Time zone of the record's local timestamps |
| `TOR_F_SCALE` | — | Tornado rating as text, such as EF1 |

## Usage and limitations

[Usage guide](../../../providers/noaa-storm-events.md).

## Catalog reference

- Availability: since 0.8
- Domain: Severe weather
- Spatial resolution: One record per county, forecast zone, or marine zone touched by an event
- Temporal resolution: One record per reported event, timestamped in the reporting office's local time
- Updates: The current year's file is updated each month
- Terms of use: <https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C00510/html>
- Citation: NOAA National Centers for Environmental Information, Storm Events Database, accessed via usdata
- Catalog date range: 1950-01-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.ncei.noaa.gov/access/storm-events-database/)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.storm_events:StormEvents`

[All NOAA datasets](../noaa.md).
