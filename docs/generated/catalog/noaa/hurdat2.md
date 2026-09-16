# Tropical cyclone best tracks

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:hurdat2` · **Released** · Included since usdata 0.12.

HURDAT2 Atlantic and Pacific Best Tracks.

## At a glance

- Files: HURDAT2 fixed-format text
- Selection: The newest revision of one whole basin file; filter track points locally
- Required inputs: Optional basin (atlantic or pacific); no dates or geographic filters
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [hurdat2](https://usdata.dev/examples/hurdat2/), [storm surge](https://usdata.dev/examples/storm-surge/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `basin` | Best-track basin: 'atlantic' (default) or 'pacific'. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `storm_id` | — | ATCF-style basin, cyclone number, and year, such as AL042021 |
| `name` | — | Storm name, or UNNAMED |
| `time` | UTC | Track-point time |
| `record_identifier` | — | Landfall (L), intensity peak (I), pressure minimum (P), and the other codes |
| `status` | — | TD, TS, HU, EX, SD, SS, LO, WV, or DB |
| `latitude` | degrees_north | Track-point latitude |
| `longitude` | degrees_east | Track-point longitude in [-180, 180] |
| `max_wind_kt` | knots | Maximum sustained 1-minute surface wind |
| `min_pressure_mb` | millibars | Minimum central pressure |
| `r34_ne_nm` | nautical miles | 34 kt wind extent, northeast quadrant |
| `r34_se_nm` | nautical miles | 34 kt wind extent, southeast quadrant |
| `r34_sw_nm` | nautical miles | 34 kt wind extent, southwest quadrant |
| `r34_nw_nm` | nautical miles | 34 kt wind extent, northwest quadrant |
| `r50_ne_nm` | nautical miles | 50 kt wind extent, northeast quadrant |
| `r50_se_nm` | nautical miles | 50 kt wind extent, southeast quadrant |
| `r50_sw_nm` | nautical miles | 50 kt wind extent, southwest quadrant |
| `r50_nw_nm` | nautical miles | 50 kt wind extent, northwest quadrant |
| `r64_ne_nm` | nautical miles | 64 kt wind extent, northeast quadrant |
| `r64_se_nm` | nautical miles | 64 kt wind extent, southeast quadrant |
| `r64_sw_nm` | nautical miles | 64 kt wind extent, southwest quadrant |
| `r64_nw_nm` | nautical miles | 64 kt wind extent, northwest quadrant |
| `max_wind_radius_nm` | nautical miles | Radius of maximum wind, best-tracked from 2021 |

## Usage and limitations

[Usage guide](../../../providers/noaa-hurdat2.md).

## Catalog reference

- Availability: since 0.12
- Domain: Tropical cyclones
- Spatial resolution: Best-track positions in tenths of a degree
- Temporal resolution: Six-hourly synoptic times, plus asynoptic records for landfalls and extremes
- Updates: Annually, after each season's post-storm reanalysis; the 2025 season was added on 2026-02-27
- Terms of use: <https://www.weather.gov/disclaimer>
- Citation: Landsea, C. W. and J. L. Franklin, 2013: Atlantic Hurricane Database Uncertainty and Presentation of a New Database Format. Mon. Wea. Rev., 141, 3576-3592
- Catalog date range: 1851-01-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.nhc.noaa.gov/data/#hurdat)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.hurdat2:Hurdat2`

[All NOAA datasets](../noaa.md).
