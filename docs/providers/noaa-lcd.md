# Local Climatological Data

Available since v0.14.0 as `noaa:lcd`. LCD uses the
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

The [hourly observations example](https://usdata.dev/datasets/noaa/lcd/)
compares hourly readings with the daily summary for the same station. NCEI
revises LCD as reports are quality-controlled.

The [hourly anomalies example](https://usdata.dev/studies/hourly-anomalies/)
compares routine reports with hourly normals in local standard time, using an
explicit ten-minute matching tolerance rather than treating reports as hourly means.

--8<-- "_snippets/upstream-revisions.md"

See the [service research notes](noaa-services.md#local-climatological-data) for dated upstream probes.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Updates, terms, and resolution: the [NCEI dataset
  record](https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C00684/html),
  whose maintenance frequency is monthly and whose use constraint is only "cite this
  dataset when used as a source", so the entry uses the agency, product, and access form
  for `citation`.
- Variables: the [LCD
  documentation](https://www.ncei.noaa.gov/data/local-climatological-data/doc/LCD_documentation.pdf)
  and the columns this guide names, with the units returned under `units=metric`. Every
  row carries 125 columns, so the list is a sample.
- Latency is empty: the record states no lag between a report and its appearance.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/lcd.md#catalog-reference).
