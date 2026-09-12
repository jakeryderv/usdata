# U.S. Climate Normals 1991-2020

Available since v0.11.0 as `noaa:climate-normals`.
Normals are 30-year averages of daily, monthly, and annual/seasonal station
statistics, served by the anonymous NCEI Access Data Service datasets
`normals-monthly-1991-2020`, `normals-daily-1991-2020`, and
`normals-annualseasonal-1991-2020`. The adapter reuses GHCN station discovery,
transport, and 50-station CSV chunks. Choose the dataset with `period`:
`monthly` (default), `daily`, or `annualseasonal`. Pass either `stations` or a
location/bbox, not both. `units` is `metric` (default) or `standard`; unknown
parameters and text queries are rejected.

Dates are optional because normals are not observations. For `daily` and
`monthly`, an optional `start`/`end` pair selects a calendar window by month
and day; the year is ignored and sent as the placeholder 2020, a leap year so
February 29 is valid. Without dates the whole year is requested. Datetimes with
an offset are converted to UTC before the month and day are taken, and a window
whose start falls after its end in the calendar (crossing the new year) is
rejected: split it into two sources. `annualseasonal` accepts no dates. Assets
carry the 1991-2020 normals period as their time bounds, not the calendar window;
the window is part of the asset id and URL.

Geographic discovery searches the selected period's dataset for stations with
normals coverage over 1991-2020 inside the box. Not every GHCN station has
normals; stations that do are listed by the [NCEI normals product page](https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals).

CSV `DATE` is `MM` for monthly and `MM-DD` for daily normals; annual/seasonal
files have no `DATE` column. Use `item.open(dtype={"DATE": "string"})` to keep
the labels as text with the pandas reader. Variables are NCEI data type codes
such as `MLY-TMAX-NORMAL`, `DLY-PRCP-NORMAL`, or `ANN-TAVG-NORMAL`; see the
[NCEI normals documentation](https://www.ncei.noaa.gov/data/normals-monthly/1991-2020/doc/Normals_MLY_Documentation_1991-2020.pdf)
for the full list. **The service does not reject unknown data types**: an
unknown code yields an empty column, so check spelling against that list.
Metric temperatures are degrees Celsius and precipitation is millimeters; the
service default is standard units, which usdata overrides with `units=metric`.
Standard-unit values retain the source's leading spaces. **`MLY-TAVG-NORMAL` is
an upstream exception**: it comes back in degrees Fahrenheit with those leading
spaces even under `units=metric` (probed 2026-09-11, when `MLY-TMAX-NORMAL`,
`MLY-TMIN-NORMAL`, `MLY-PRCP-NORMAL`, `DLY-TAVG-NORMAL`, and `ANN-TAVG-NORMAL`
all converted). Convert it yourself before comparing it with Celsius
observations, as the [anomalies notebook](../examples/climate-anomalies/example.md)
does. Station columns are included with `includeStationLocation=1`.

Normals are republished about once a decade; the 1991-2020 files can still be
corrected. Retain the cache as well as the manifest and lockfile. See the
[service research notes](noaa-services.md#us-climate-normals) for dated probes.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/climate-normals.md#catalog-reference).
