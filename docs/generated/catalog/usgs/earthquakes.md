# Earthquake events

<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

`usgs:earthquakes` · **Released** · Included since usdata 0.19.

Earthquake Catalog (ComCat).

## At a glance

- Files: CSV
- Selection: Events inside an inclusive UTC window and optional box, magnitude, and depth bounds
- Required inputs: Both timestamps; optionally a location or bbox and magnitude or depth bounds
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- On usdata.dev: [Earthquake events](https://usdata.dev/datasets/usgs/earthquakes/), with a walkthrough

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `max_depth` | Deepest depth to include, in kilometers, inclusive. |
| `max_magnitude` | Largest magnitude to include, inclusive. |
| `min_depth` | Shallowest depth to include, in kilometers, inclusive. |
| `min_magnitude` | Smallest magnitude to include, inclusive. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `time` | ISO 8601 UTC | Origin time of the event |
| `latitude` | degrees north | Epicenter latitude |
| `longitude` | degrees east | Epicenter longitude |
| `depth` | km | Hypocenter depth below sea level |
| `mag` | magnitude | Magnitude on the scale magType names |
| `magType` | — | Magnitude scale, such as ml or mw |
| `place` | — | Nearby place and distance, as a phrase |
| `type` | — | Event type; earthquake unless otherwise |
| `status` | — | automatic or reviewed |
| `updated` | ISO 8601 UTC | When the event was last revised |

## Usage and limitations

[Usage guide](../../../providers/usgs-earthquakes.md).

## Catalog reference

- Availability: since 0.19
- Domain: Natural hazards
- Spatial resolution: Point epicenters in decimal degrees, as located by the contributing network
- Temporal resolution: Origin times to the millisecond
- Updates: Continuous; events post automatically from contributing networks and are superseded by reviewed versions
- Terms of use: <https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits>
- Citation: U.S. Geological Survey, Earthquake Hazards Program, 2017, Advanced National Seismic System (ANSS) Comprehensive Catalog of Earthquake Events and Products, doi:10.5066/F7MS3QZH
- Geographic bounds (WGS84): west -180°, south -90°, east 180°, north 90°
- Catalog date range: 1900-01-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://earthquake.usgs.gov/fdsnws/event/1/)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.usgs.earthquakes:Earthquakes`

[All USGS datasets](../usgs.md).
