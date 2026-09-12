# Local Climatological Data

Available from source for the unreleased v0.14.0 as `noaa:lcd`. LCD uses the
anonymous NCEI Access Data Service dataset `local-climatological-data`, reusing
GHCN station discovery, pagination, and CSV chunking, with ten stations per
asset instead of fifty because hourly rows are wide. Require both dates and
either `stations` or a location/bbox, not both. `units` is `metric` (default)
or `standard`; unknown parameters and text queries are rejected.

Station ids are the eleven-digit LCD identifiers the search service returns,
such as `72353013967` for Oklahoma City's Will Rogers World Airport: a
five-digit WMO index followed by a six-digit WBAN number. Other forms such as
`13967` or the GHCN id `USW00013967` are accepted by the service but return a
header with no rows, so use a geographic query to discover the exact ids.

Dates select whole calendar days, and every row's `DATE` is the station's local
standard time without an offset, not UTC. A day of observations is typically
sixty rows: `REPORT_TYPE` distinguishes hourly METAR reports (`FM-15`), special
reports (`FM-16`), synoptic reports (`FM-12`), the daily summary (`SOD`), and,
at month end, the monthly summary (`SOM`). Filter by report type before
aggregating, and expect `REPORT_TYPE` values to carry trailing spaces. Without
`variables` every row carries 125 columns; naming `variables` such as
`HourlyDryBulbTemperature` or `DailyPrecipitation` keeps only those, plus the
station, date, report type, and source columns. Values can carry quality
suffixes such as `s` and precipitation can be `T` for trace, so coerce numbers
explicitly. Consult the [LCD documentation](https://www.ncei.noaa.gov/data/local-climatological-data/doc/LCD_documentation.pdf)
for each field's unit under `units=metric` and its flags.

```sh
uv run usdata fetch noaa:lcd -p stations=72353013967 \
  --start 2024-05-06 --end 2024-05-06 \
  --vars HourlyDryBulbTemperature,HourlyPrecipitation --dry-run
```

The [hourly observations example](https://usdata.dev/examples/hourly-observations/)
compares hourly readings with the daily summary for the same station. NCEI
revises LCD as reports are quality-controlled, so the same request can return
different bytes later; keep the cache with the manifest and lockfile.

See the [service research notes](noaa-services.md#local-climatological-data) for dated upstream probes.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/lcd.md#catalog-reference).
