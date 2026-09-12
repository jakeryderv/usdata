# Coastal tide predictions

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:coops-tide-predictions` · **Source only** · Install from [source](../../../project.md#source-installation) to use this dataset.

CO-OPS Tide Predictions.

## At a glance

- Files: CSV
- Selection: Predictions for one station and datum on a chosen interval; at most a year
- Required inputs: Station, datum, and both minute-aligned timestamps; optional interval
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [storm surge](https://usdata.dev/examples/storm-surge/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `datum` | Required vertical datum: CRD, IGLD, LWD, MHHW, MHW, MLLW, MLW, MSL, MTL, NAVD, STND. |
| `interval` | 6 (default), 1, 5, 10, 15, 30, or 60 minutes; h (hourly); hilo (high/low). |
| `station` | Required seven-digit CO-OPS station id, for example '8518750'. |
| `units` | metric (default) or english. |

## Usage and limitations

[Usage guide](../../../providers/noaa-coops-predictions.md).

## Catalog reference

- Availability: Source only · intended for 0.14
- Domain: Sea level and tides
- Coverage: not specified in the catalog
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://api.tidesandcurrents.noaa.gov/api/prod/)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.coops:CoopsTidePredictions`

[All NOAA datasets](../noaa.md).
