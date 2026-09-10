# Coastal water levels

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:coops-water-levels` · **Released** · Included since usdata 0.10.

CO-OPS Observed Water Levels.

## At a glance

- Files: CSV
- Selection: Six-minute observations for one station and datum; at most 28 days
- Required inputs: Station, datum, and both minute-aligned timestamps
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [coastal water levels](../../../../examples/coastal-water-levels/README.md)

## Usage and limitations

<!-- dataset-usage -->
[Usage guide](../../../providers/noaa-coops.md).

## Catalog reference

- Availability: since 0.10
- Domain: Sea level and tides
- Coverage: not specified in the catalog
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://api.tidesandcurrents.noaa.gov/api/prod/)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.coops:CoopsWaterLevels`

[All NOAA datasets](../noaa.md).
