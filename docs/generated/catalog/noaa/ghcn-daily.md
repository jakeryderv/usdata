# Daily station weather

<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

`noaa:ghcn-daily` · **Released** · Included since usdata 0.2.

GHCN-Daily Station Observations.

## At a glance

- Files: CSV
- Selection: Station observations within inclusive calendar dates; selected elements
- Required inputs: Both dates; station IDs or a geographic query
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [How can I preserve weather and streamflow inputs together?](https://usdata.dev/examples/weather-and-streamflow/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `stations` | Station ids, comma-separated or a list; otherwise a location selects them. |
| `units` | metric (default) or standard. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `PRCP` | mm | Precipitation total (metric units) |
| `TMAX` | degrees Celsius | Maximum temperature (metric units) |
| `TMIN` | degrees Celsius | Minimum temperature (metric units) |
| `SNOW` | mm | Snowfall (metric units) |
| `SNWD` | mm | Snow depth (metric units) |

## Usage and limitations

[Usage guide](../../../providers/noaa-ghcn.md).

## Catalog reference

- Availability: since 0.2
- Domain: Surface weather
- Spatial resolution: Land surface stations; more than 100,000 stations in 180 countries and territories
- Temporal resolution: Daily
- Updates: Daily, reconstructed each weekend from more than 25 data source components
- Latency: Real-time streams are replaced by archive-ready sources 45 to 60 days after the end of a month
- Terms of use: <https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C00861/html>
- Citation: Menne, M.J., I. Durre, R.S. Vose, B.E. Gleason, and T.G. Houston, 2012: An overview of the Global Historical Climatology Network-Daily Database. Journal of Atmospheric and Oceanic Technology, 29, 897-910, doi:10.1175/JTECH-D-11-00103.1
- Geographic bounds (WGS84): west -180°, south -90°, east 180°, north 90°
- Catalog date range: 1763-01-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.ghcnd:GhcnDaily`

[All NOAA datasets](../noaa.md).
