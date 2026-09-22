# 30-year station climate normals

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:climate-normals` · **Released** · Included since usdata 0.11.

U.S. Climate Normals 1991-2020.

## At a glance

- Files: CSV
- Selection: Hourly, daily, monthly, or annual/seasonal normals per station; optional month-day window except annual/seasonal; hourly returns whole days
- Required inputs: Station IDs or a geographic query; dates optional
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- Examples: [climate normals](https://usdata.dev/examples/climate-normals/), [climate anomalies](https://usdata.dev/examples/climate-anomalies/), [hourly anomalies](https://usdata.dev/examples/hourly-anomalies/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `period` | monthly (default), daily, annualseasonal, or hourly. |
| `stations` | Station ids, comma-separated or a list; otherwise a location selects them. |
| `units` | metric (default) or standard. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `HLY-TEMP-NORMAL` | degrees Celsius | Hourly normal mean temperature (metric units); local standard time |
| `MLY-TMAX-NORMAL` | degrees Celsius | Monthly normal maximum temperature |
| `MLY-TMIN-NORMAL` | degrees Celsius | Monthly normal minimum temperature |
| `MLY-PRCP-NORMAL` | mm | Monthly normal precipitation total |
| `MLY-TAVG-NORMAL` | degrees Fahrenheit | Monthly normal mean temperature; units=metric does not convert it |
| `MLY-DUTR-NORMAL` | degrees Fahrenheit | Monthly normal diurnal temperature range; read it from units=standard |
| `MLY-TAVG-STDDEV` | degrees Fahrenheit | Standard deviation of monthly mean temperature; read it from units=standard |
| `MLY-TMAX-STDDEV` | degrees Fahrenheit | Standard deviation of monthly maximum temperature; read it from units=standard |
| `DLY-TAVG-NORMAL` | degrees Celsius | Daily normal mean temperature |
| `DLY-PRCP-NORMAL` | mm | Daily normal precipitation |
| `ANN-TAVG-NORMAL` | degrees Celsius | Annual normal mean temperature |

## Usage and limitations

[Usage guide](../../../providers/noaa-normals.md).

## Catalog reference

- Availability: since 0.11
- Domain: Climate
- Spatial resolution: U.S. land surface stations with 1991-2020 normals coverage
- Temporal resolution: Hourly, daily, monthly, or annual and seasonal normals, chosen with the period parameter
- Updates: As needed; the normals are republished about once a decade
- Terms of use: <https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals>
- Citation: Palecki, Michael; Durre, Imke; Applequist, Scott; Arguez, Anthony; Lawrimore, Jay (2021). U.S. Climate Normals 2020 (1991-2020). NOAA National Centers for Environmental Information; cite the record for the period used
- Geographic bounds (WGS84): west -180°, south -90°, east 180°, north 90°
- Catalog date range: 1991-01-01 to 2020-12-31
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.normals:ClimateNormals`

[All NOAA datasets](../noaa.md).
