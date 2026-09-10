# Annual station climate

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:gsoy` · **Released** · Included since usdata 0.10.

Global Summary of the Year.

## At a glance

- Files: CSV
- Selection: Complete UTC calendar years touched by the query; station and element filters
- Required inputs: Both dates; station IDs or a geographic query
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [annual climate](../../../../examples/annual-climate/README.md)

## Usage and limitations

<!-- dataset-usage -->
[Usage guide](../../../providers/noaa-gsoy.md).

## Catalog reference

- Availability: since 0.10
- Domain: Surface weather
- Geographic bounds (WGS84): west -180°, south -90°, east 180°, north 90°
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.ncei.noaa.gov/access/search/data-search/global-summary-of-the-year)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.gsoy:GlobalSummaryYearly`

[All NOAA datasets](../noaa.md).
