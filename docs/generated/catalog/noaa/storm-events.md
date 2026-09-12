# Storm Events details

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:storm-events` · **Released** · Included since usdata 0.8.

Storm Events Database.

## At a glance

- Files: gzip CSV
- Selection: Whole annual archives; filter rows locally after downloading
- Required inputs: Both dates (selects the containing years)
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [storm events](../../../examples/storm-events/example.md)

## Usage and limitations

[Usage guide](../../../providers/noaa-storm-events.md).

## Catalog reference

- Availability: since 0.8
- Domain: Severe weather
- Catalog date range: 1950-01-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.ncei.noaa.gov/access/storm-events-database/)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.storm_events:StormEvents`

[All NOAA datasets](../noaa.md).
