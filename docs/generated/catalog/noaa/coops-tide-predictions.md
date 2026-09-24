# Coastal tide predictions

<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

`noaa:coops-tide-predictions` · **Released** · Included since usdata 0.14.

CO-OPS Tide Predictions.

## At a glance

- Files: CSV
- Selection: Predictions for one station and datum on a chosen interval; at most a year
- Required inputs: Station, datum, and both minute-aligned timestamps; optional interval
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- On usdata.dev: [Coastal tide predictions](https://usdata.dev/datasets/noaa/coops-tide-predictions/), with a walkthrough
- Studies: [How high was Hurricane Helene's storm surge at Cedar Key?](https://usdata.dev/studies/storm-surge/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `datum` | Required vertical datum: CRD, IGLD, LWD, MHHW, MHW, MLLW, MLW, MSL, MTL, NAVD, STND. |
| `interval` | 6 (default), 1, 5, 10, 15, 30, or 60 minutes; h (hourly); hilo (high/low). |
| `station` | Required seven-digit CO-OPS station id, for example '8518750'. |
| `units` | metric (default) or english. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `Date Time` | UTC | Prediction time, requested with time_zone=gmt |
| `Prediction` | meters | Predicted tide height on the requested datum (metric units) |
| `Type` | — | H or L, on the hilo interval only |

## Usage and limitations

[Usage guide](../../../providers/noaa-coops-predictions.md).

## Catalog reference

- Availability: since 0.14
- Domain: Sea level and tides
- Spatial resolution: One tide station per request
- Temporal resolution: Six minutes by default; 1, 5, 10, 15, 30, or 60 minute steps, hourly, or high/low
- Updates: Computed on request from the station's harmonic constituents, which NOAA revises occasionally
- Longest query window: 366 days
- Terms of use: <https://tidesandcurrents.noaa.gov/disclaimers.html>
- Citation: NOAA National Ocean Service, Center for Operational Oceanographic Products and Services, tide predictions, accessed via usdata
- Coverage: not specified in the catalog
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://api.tidesandcurrents.noaa.gov/api/prod/)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.coops:CoopsTidePredictions`

[All NOAA datasets](../noaa.md).
