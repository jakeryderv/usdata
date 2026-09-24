<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

## Reference

`noaa:storm-events` · **Released** · Included since usdata 0.8. Storm Events Database.

### At a glance

- Files: gzip CSV
- Selection: Whole annual archives of one table; filter rows locally after downloading
- Required inputs: Both dates (selects the containing years); optionally table
- Open locally: `usdata[pandas]` · [Reader guide](../reference/readers.md)
- On usdata.dev: [Storm Events details, fatalities, and locations](https://usdata.dev/datasets/noaa/storm-events/), with a walkthrough
- Studies: [What did radar and satellites show around a reported tornado?](https://usdata.dev/studies/event-context/); [Which severe reports came with rotation and lightning?](https://usdata.dev/studies/tornado-classification/); [For one Oklahoma tornado, do the two report archives agree on when and where it was, and what did radar, lightning, and the model analysis show at that place and time?](https://usdata.dev/studies/severe-weather-case-study/); [How long before the 6 May 2024 Osage County tornado was a tornado warning issued?](https://usdata.dev/studies/warning-lead-time/); [Which Oklahoma counties hit by a tornado on 6 May 2024 were under a federal disaster declaration?](https://usdata.dev/studies/disaster-declarations/)

### Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `table` | Annual table: details (default, one row per event), fatalities (one row per death), or locations (points per event, from 1996); EVENT_ID joins them. |

### Variables

| Variable | Units | Meaning |
|---|---|---|
| `EVENT_ID` | — | Identifier of one event record |
| `EPISODE_ID` | — | Identifier grouping the events of one storm episode |
| `CZ_TYPE` | — | County (C), forecast zone (Z), or marine (M) record |
| `CZ_FIPS` | — | County or zone code; not always a county FIPS code |
| `CZ_TIMEZONE` | — | Time zone of the record's local timestamps |
| `TOR_F_SCALE` | — | Tornado rating as text, such as EF1 |

### Catalog facts

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
