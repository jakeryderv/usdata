# Global tropical cyclone best tracks

<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

`noaa:ibtracs` · **Released** · Included since usdata 0.20.

IBTrACS Global Tropical Cyclone Tracks.

## At a glance

- Files: CSV with a units row, NetCDF4
- Selection: One whole subset file per query, from the newest or a pinned product version
- Required inputs: Required subset; optional format and version; no dates or geographic filters
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- On usdata.dev: [Global tropical cyclone best tracks](https://usdata.dev/datasets/noaa/ibtracs/), with a walkthrough

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `format` | File format: csv (default) or netcdf, case-insensitive. |
| `subset` | Required subset: all, active, last3years, since1980, or a basin (na, ep, wp, ni, si, sp, or sa), case-insensitive. |
| `version` | Product version such as v04r01; the newest published one by default. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `sid` | — | IBTrACS serial id, such as 2004086S29318; SID in the CSV |
| `season` | year | Season the storm is assigned to |
| `number` | — | Storm number within the season |
| `basin` | — | Basin at this point: NA, EP, WP, NI, SI, SP, or SA |
| `subbasin` | — | Sub-basin at this point, or MM when none applies |
| `name` | — | Storm name, or UNNAMED |
| `time` | UTC | Track-point time; ISO_TIME in the CSV |
| `nature` | — | Nature of the cyclone: TS, ET, SS, DS, NR, or MX |
| `lat` | degrees_north | Track-point latitude |
| `lon` | degrees_east | Track-point longitude in [-180, 180] |
| `wmo_wind` | knots | Maximum sustained wind from the responsible WMO agency, in that agency's averaging period |
| `wmo_pres` | millibars | Minimum central pressure from the responsible WMO agency |
| `wmo_agency` | — | The WMO agency responsible for the storm at this point |
| `track_type` | — | main, PROVISIONAL, or a spur track merged, split, or otherwise set aside |
| `dist2land` | km | Distance to land at this point |
| `landfall` | km | Minimum distance to land before the next point; 0 marks a landfall |
| `iflag` | — | One interpolation flag per agency: original, interpolated, or filled |
| `usa_wind` | knots | Maximum sustained 1-minute wind from the U.S. agency |
| `usa_pres` | millibars | Minimum central pressure from the U.S. agency |
| `usa_status` | — | U.S. agency status, such as TD, TS, HU, or EX |
| `usa_sshs` | — | Saffir-Simpson category from the U.S. wind; -5 to 5, with the negatives for non-hurricane statuses |
| `usa_rmw` | nautical miles | Radius of maximum wind from the U.S. agency |
| `usa_r34` | nautical miles | 34 kt wind extent by quadrant; USA_R34_NE through USA_R34_NW in the CSV |
| `storm_speed` | knots | Storm translation speed |
| `storm_dir` | degrees | Storm translation direction |

## Usage and limitations

[Usage guide](../../../providers/noaa-ibtracs.md).

## Catalog reference

- Availability: since 0.20
- Domain: Tropical cyclones
- Spatial resolution: Positions to a tenth of a degree
- Temporal resolution: Three-hourly points, interpolated between the agencies' six-hourly best tracks
- Updates: Files are rebuilt in place as agencies deliver best tracks, stamped with the build date; the v04r01 change log records twenty-three additions and corrections between 2024-06-21 and 2026-07-31
- Terms of use: <https://www.ncei.noaa.gov/products/international-best-track-archive>
- Citation: Gahtan, J., K. R. Knapp, C. J. Schreck, H. J. Diamond, J. P. Kossin, and M. C. Kruk, 2024: International Best Track Archive for Climate Stewardship (IBTrACS) Project, Version 4r01. NOAA National Centers for Environmental Information, doi:10.25921/82ty-9e16. Knapp, K. R., M. C. Kruk, D. H. Levinson, H. J. Diamond, and C. J. Neumann, 2010: The International Best Track Archive for Climate Stewardship (IBTrACS). Bull. Amer. Meteor. Soc., 91, 363-376
- Catalog date range: 1842-10-25 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.ncei.noaa.gov/products/international-best-track-archive)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.ibtracs:Ibtracs`

[All NOAA datasets](../noaa.md).
