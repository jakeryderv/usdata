# Sea-surface temperature

<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

`noaa:coastwatch-sst` · **Released** · Included since usdata 0.5.

CoastWatch Blended Sea Surface Temperature.

## At a glance

- Files: CSV with units row
- Selection: Grid centers and timestamps inside the requested bounds; optional stride
- Required inputs: BBox or location, and both timestamps
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [How warm was the sea in a small area?](https://usdata.dev/examples/sst-analysis/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `stride` | Positive integer subsampling both spatial axes; default 1. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `analysed_sst` | degree_C | Analysed sea surface temperature |
| `analysis_error` | degree_C | Estimated error of the analysis |
| `sea_ice_fraction` | 1 | Sea ice area fraction |
| `mask` | — | Source mask flags; consult the source metadata for the codes |

## Usage and limitations

[Usage guide](../../../providers/noaa-coastwatch.md).

## Catalog reference

- Availability: since 0.5
- Domain: Satellite oceanography
- Spatial resolution: 0.05 degree global grid, about 5 km
- Temporal resolution: Daily
- Updates: Daily
- Terms of use: <https://coastwatch.noaa.gov/erddap/info/noaacwBLENDEDsstDNDaily/index.html>
- Citation: NOAA/NESDIS Office of Satellite Products and Operations, Geo-polar Blended Sea Surface Temperature Analysis (noaacwBLENDEDsstDNDaily), accessed via usdata
- Geographic bounds (WGS84): west -179.975°, south -89.975°, east 179.975°, north 89.975°
- Catalog date range: 2019-07-22 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://coastwatch.noaa.gov/erddap/griddap/noaacwBLENDEDsstDNDaily.html)
- License: GHRSST free and open data
- Transport: `erddap`
- Adapter: `usdata.providers.noaa.coastwatch:CoastwatchSst`

[All NOAA datasets](../noaa.md).
