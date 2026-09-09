# Monthly station climate

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:gsom` · **Released** · Included since usdata 0.7.

Global Summary of the Month.

## At a glance

- Files: CSV
- Selection: Complete UTC calendar months touched by the query; station and element filters
- Required inputs: Both dates; station IDs or a geographic query
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [monthly climate](../../../../examples/monthly-climate/example.ipynb)

## Usage and limitations

<!-- dataset-usage -->
[Usage guide](../../../providers/noaa-gsom.md).

## Catalog reference

- Availability: since 0.7
- Domain: Surface weather
- Geographic bounds (WGS84): west -180°, south -90°, east 180°, north 90°
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.ncei.noaa.gov/access/search/data-search/global-summary-of-the-month)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.gsom:GlobalSummaryMonthly`

[All NOAA datasets](../noaa.md).
