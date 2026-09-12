# 30-year station climate normals

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:climate-normals` · **Source only** · Install from [source](../../../project.md#source-installation) to use this dataset.

U.S. Climate Normals 1991-2020.

## At a glance

- Files: CSV
- Selection: Monthly, daily, or annual/seasonal normals per station; optional month-day window for daily and monthly
- Required inputs: Station IDs or a geographic query; dates optional
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [climate normals](../../../examples/climate-normals/README.md)

## Usage and limitations

[Usage guide](../../../providers/noaa-normals.md).

## Catalog reference

- Availability: Source only · intended for 0.11
- Domain: Climate
- Geographic bounds (WGS84): west -180°, south -90°, east 180°, north 90°
- Catalog date range: 1991-01-01 to 2020-12-31
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.normals:ClimateNormals`

[All NOAA datasets](../noaa.md).
