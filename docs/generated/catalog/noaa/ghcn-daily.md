# Daily station weather

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:ghcn-daily` · **Released** · Included since usdata 0.2.

GHCN-Daily Station Observations.

## At a glance

- Files: CSV
- Selection: Station observations within inclusive calendar dates; selected elements
- Required inputs: Both dates; station IDs or a geographic query
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [weather and streamflow](../../../examples/weather-and-streamflow/example.md)

## Usage and limitations

[Usage guide](../../../providers/noaa-ghcn.md).

## Catalog reference

- Availability: since 0.2
- Domain: Surface weather
- Geographic bounds (WGS84): west -180°, south -90°, east 180°, north 90°
- Catalog date range: 1763-01-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.ghcnd:GhcnDaily`

[All NOAA datasets](../noaa.md).
