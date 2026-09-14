# SPC tornado database

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:spc-tornado-reports` · **Source only** · Install from [source](../../../project.md#source-installation) to use this dataset.

SPC Tornado Reports.

## At a glance

- Files: CSV
- Selection: Whole annual, half-decade, or decade files; filter rows locally after downloading
- Required inputs: Both dates (selects the files covering those years)
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [spc tornadoes](https://usdata.dev/examples/spc-tornadoes/)

## Parameters

This dataset accepts no provider-specific parameters.

## Usage and limitations

[Usage guide](../../../providers/noaa-spc-tornado.md).

## Catalog reference

- Availability: Source only · intended for 0.15
- Domain: Severe weather
- Catalog date range: 1950-01-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.spc.noaa.gov/wcm/#data)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.spc:SpcTornadoReports`

[All NOAA datasets](../noaa.md).
