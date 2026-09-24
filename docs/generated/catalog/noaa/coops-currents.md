# Coastal current speed and direction

<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

`noaa:coops-currents` · **Released** · Included since usdata 0.24.

CO-OPS Observed Currents.

## At a glance

- Files: CSV
- Selection: Native six-minute observations for one station and explicit bin; at most 28 days
- Required inputs: Alphanumeric station, positive bin, and both minute-aligned timestamps
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [How did currents change at Cape Henry on 6 May 2025?](https://usdata.dev/examples/coastal-currents/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `bin` | Required positive bin number; 0 (all bins) is not supported. |
| `station` | Required alphanumeric CO-OPS currents station id, for example 'cb0102'. |
| `units` | metric (default, cm/s) or english (knots). |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `Date Time` | UTC | Observation time, requested with time_zone=gmt |
| `Speed` | cm/s | Observed current speed in metric units; knots with english units |
| `Direction` | degrees | Observed current direction |
| `Bin` | — | Requested bin number, not a depth measurement |

## Usage and limitations

[Usage guide](../../../providers/noaa-coops-currents.md).

## Catalog reference

- Availability: since 0.24
- Domain: Ocean physics
- Spatial resolution: One current-meter station and bin per request; bin depths depend on deployment
- Temporal resolution: Six-minute observations
- Longest query window: 28 days
- Terms of use: <https://tidesandcurrents.noaa.gov/disclaimers.html>
- Citation: NOAA National Ocean Service, CO-OPS observed currents, accessed via usdata
- Coverage: not specified in the catalog
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://api.tidesandcurrents.noaa.gov/api/prod/)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.coops:CoopsCurrents`

[All NOAA datasets](../noaa.md).
