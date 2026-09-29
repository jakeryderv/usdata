<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

## Reference

`noaa:gsom-station-files` · **Source only** · Install from [source](../install.md#source-installation) to use this dataset. Global Summary of the Month Station Files.

### At a glance

- Files: CSV
- Selection: One whole file per named station, every month and element it holds
- Required inputs: Station IDs; no dates, geographic filters, or variables
- Open locally: `usdata[pandas]` · [Reader guide](../reference/readers.md)
- On usdata.dev: [Whole monthly station records, one file per station](https://usdata.dev/datasets/noaa/gsom-station-files/), with a walkthrough

### Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `stations` | Required GHCN station id(s): one, a list, or comma-separated. |

### Variables

| Variable | Units | Meaning |
|---|---|---|
| `PRCP` | mm | Monthly precipitation total |
| `SNOW` | mm | Monthly snowfall total |
| `SNOW_ATTRIBUTES` | — | Days missing, measurement, quality, and source flags for SNOW |
| `TAVG` | degrees Celsius | Monthly mean temperature |

### Catalog facts

- Availability: Source only · intended for 0.33
- Domain: Surface weather
- Spatial resolution: Land surface stations, derived from GHCN-Daily
- Temporal resolution: Monthly
- Updates: Weekly
- Terms of use: <https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C00946/html>
- Citation: Lawrimore, Jay H.; Ray, Ron; Applequist, Scott; Korzeniewski, Bryant; Menne, Matthew J. (2016): Global Summary of the Month (GSOM), Version 1. NOAA National Centers for Environmental Information. https://doi.org/10.7289/V5QV3JJ5
- Geographic bounds (WGS84): west -180°, south -90°, east 180°, north 90°
- Catalog date range: 1763-01-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.ncei.noaa.gov/data/global-summary-of-the-month/)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.gsom_files:GsomStationFiles`
