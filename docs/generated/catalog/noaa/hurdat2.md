# Tropical cyclone best tracks

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:hurdat2` · **Source only** · Install from [source](../../../project.md#source-installation) to use this dataset.

HURDAT2 Atlantic and Pacific Best Tracks.

## At a glance

- Files: HURDAT2 fixed-format text
- Selection: The newest revision of one whole basin file; filter track points locally
- Required inputs: Optional basin (atlantic or pacific); no dates or geographic filters
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [hurdat2](../../../examples/hurdat2/README.md)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `basin` | Best-track basin: 'atlantic' (default) or 'pacific'. |

## Usage and limitations

[Usage guide](../../../providers/noaa-hurdat2.md).

## Catalog reference

- Availability: Source only · intended for 0.12
- Domain: Tropical cyclones
- Catalog date range: 1851-01-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.nhc.noaa.gov/data/#hurdat)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.hurdat2:Hurdat2`

[All NOAA datasets](../noaa.md).
