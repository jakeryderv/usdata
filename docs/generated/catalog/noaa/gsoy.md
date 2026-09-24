# Annual station climate

<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

`noaa:gsoy` · **Released** · Included since usdata 0.10.

Global Summary of the Year.

## At a glance

- Files: CSV
- Selection: Complete UTC calendar years touched by the query; station and element filters
- Required inputs: Both dates; station IDs or a geographic query
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- On usdata.dev: [Annual station climate](https://usdata.dev/datasets/noaa/gsoy/), with a walkthrough

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `stations` | Station ids, comma-separated or a list; otherwise a location selects them. |
| `units` | metric (default) or standard. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `PRCP` | mm | Annual precipitation total (metric units) |
| `TAVG` | degrees Celsius | Annual mean temperature (metric units) |

## Usage and limitations

[Usage guide](../../../providers/noaa-gsoy.md).

## Catalog reference

- Availability: since 0.10
- Domain: Surface weather
- Spatial resolution: Land surface stations, derived from GHCN-Daily
- Temporal resolution: Annual
- Updates: Weekly
- Terms of use: <https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C00947/html>
- Citation: Lawrimore, Jay H.; Ray, Ron; Applequist, Scott; Korzeniewski, Bryant; Menne, Matthew J. (2016): Global Summary of the Year (GSOY), Version 1. NOAA National Centers for Environmental Information. https://doi.org/10.7289/JWPF-Y430
- Geographic bounds (WGS84): west -180°, south -90°, east 180°, north 90°
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.ncei.noaa.gov/access/search/data-search/global-summary-of-the-year)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.gsoy:GlobalSummaryYearly`

[All NOAA datasets](../noaa.md).
