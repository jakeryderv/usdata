# Coastal water levels

<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

`noaa:coops-water-levels` · **Released** · Included since usdata 0.10.

CO-OPS Observed Water Levels.

## At a glance

- Files: CSV
- Selection: Six-minute observations for one station and datum; at most 28 days
- Required inputs: Station, datum, and both minute-aligned timestamps
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- On usdata.dev: [Coastal water levels](https://usdata.dev/datasets/noaa/coops-water-levels/), with a walkthrough
- Studies: [How high was Hurricane Helene's storm surge at Cedar Key?](https://usdata.dev/studies/storm-surge/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `datum` | Required vertical datum: CRD, IGLD, LWD, MHHW, MHW, MLLW, MLW, MSL, MTL, NAVD, STND. |
| `station` | Required seven-digit CO-OPS station id, for example '8518750'. |
| `units` | metric (default) or english. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `Date Time` | UTC | Observation time, requested with time_zone=gmt |
| `Water Level` | meters | Observed water level on the requested datum (metric units) |
| `Sigma` | meters | Standard deviation of the one-second samples in the interval |
| `O or I (for verified)` | — | Count of outliers, or the inference flag on verified data |
| `F` | — | Flat-tolerance limit flag |
| `R` | — | Rate-of-change limit flag |
| `L` | — | Expected-height limit flag: 1 when the value passed the maximum or minimum expected water level |
| `Quality` | — | p for preliminary or v for verified |

## Usage and limitations

[Usage guide](../../../providers/noaa-coops.md).

## Catalog reference

- Availability: since 0.10
- Domain: Sea level and tides
- Spatial resolution: One National Water Level Observation Network station per request
- Temporal resolution: Six minutes
- Updates: Six-minute observations as the station reports; NOAA verifies the past month's data monthly
- Longest query window: 28 days
- Terms of use: <https://tidesandcurrents.noaa.gov/disclaimers.html>
- Citation: NOAA National Ocean Service, Center for Operational Oceanographic Products and Services, observed water levels, accessed via usdata
- Coverage: not specified in the catalog
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://api.tidesandcurrents.noaa.gov/api/prod/)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.coops:CoopsWaterLevels`

[All NOAA datasets](../noaa.md).
