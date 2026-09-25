# U.S. Climate Normals 1991-2020

Available since v0.11.0 as `noaa:climate-normals`.
Normals are 30-year averages of hourly, daily, monthly, and annual/seasonal station
statistics, served by the anonymous NCEI Access Data Service datasets
`normals-monthly-1991-2020`, `normals-daily-1991-2020`, and
`normals-annualseasonal-1991-2020`, plus `normals-hourly-1991-2020`. The adapter reuses GHCN station discovery,
transport, and 50-station CSV chunks. Choose the dataset with `period`:
`monthly` (default), `daily`, `annualseasonal`, or `hourly`. Hourly support is
available since v0.23.0. Pass either `stations` or a
location/bbox, not both. `units` is `metric` (default) or `standard`; unknown
parameters and text queries are rejected.

Dates are optional because normals are not observations. For `hourly`, `daily`, and
`monthly`, an optional `start`/`end` pair selects a calendar window by month
and day; the year is ignored and sent as the placeholder 2020, a leap year so
February 29 is valid. Without dates the whole year is requested. Datetimes with
an offset are converted to UTC before the month and day are taken, and a window
whose start falls after its end in the calendar (crossing the new year) is
rejected: split it into two sources. `annualseasonal` accepts no dates. Assets
carry the 1991-2020 normals period as their time bounds, not the calendar window;
the window is part of the asset id and URL.

## Hourly normals

`period: hourly` returns every hour of the selected calendar days, not an
instant range. The same UTC normalization of query dates applies before the
month and day are selected; use plain dates to avoid a timezone shift changing
the day. Returned `DATE` labels are `MM-DDTHH:MM:SS` in the station's **local
standard time**, without a year or offset. They are not UTC and do not follow
daylight saving time. Keep them as text with `item.open_csv(dtype={"DATE": "string"})`
and align them explicitly with observations.

Hourly normals have **no February 29 values**. A February 28–March 1 request
returns 48 hours; a February 29-only request has no hourly values. The adapter
does not interpolate missing days. NCEI computes each normal from a 15-day
window around that calendar day across 30 years, rather than only that date's
30 observations. See the [hourly documentation](https://www.ncei.noaa.gov/pub/data/cdo/documentation/normals-hourly-1991-2020_documentation.pdf).

```sh
usdata fetch noaa:climate-normals -p period=hourly -p stations=USW00013967 \
  --start 2024-05-06 --end 2024-05-06 --vars HLY-TEMP-NORMAL
```

`HLY-TEMP-NORMAL` was checked in both unit systems on 2026-09-21: all 24
values for May 6 at `USW00013967` converted correctly from Fahrenheit to
Celsius under `units=metric`. This does not establish conversion correctness
for other hourly variables. NCEI documents `-9999` as missing or insufficient
data; mask it before arithmetic. The [hourly anomalies example](https://usdata.dev/studies/hourly-anomalies/)
matches routine LCD observations to the nearest normal within ten minutes,
reports unmatched values, and verifies restoration into a fresh cache.

## Station discovery and values

Geographic discovery searches the selected period's dataset for stations with
normals coverage over 1991-2020 inside the box. Not every GHCN station has
normals; stations that do are listed by the [NCEI normals product page](https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals).

CSV `DATE` is `MM` for monthly and `MM-DD` for daily normals; annual/seasonal
files have no `DATE` column. Use `item.open_csv(dtype={"DATE": "string"})` to keep
the labels as text with the pandas reader. Variables are NCEI data type codes
such as `MLY-TMAX-NORMAL`, `DLY-PRCP-NORMAL`, or `ANN-TAVG-NORMAL`; see the
[NCEI normals documentation](https://www.ncei.noaa.gov/data/normals-monthly/1991-2020/doc/Normals_MLY_Documentation_1991-2020.pdf)
for the full list. **The service does not reject unknown data types**: an
unknown code yields an empty column, so check spelling against that list.
The service default is standard units, which usdata overrides with
`units=metric`; standard-unit values retain the source's leading spaces.
**`units=metric` is not uniformly correct**, and `variables` reaches the whole
NCEI data-type list, so verify any code you have not probed rather than assuming
Celsius. Two failures were reproduced on 2026-09-11 at `USW00013967` and
`USW00014739`:

- **`MLY-TAVG-NORMAL` is not converted at all.** It returns the same
  space-padded degrees-Fahrenheit value under both `units=metric` and
  `units=standard`. Convert it yourself before comparing it with Celsius
  observations, as the [anomalies notebook](https://usdata.dev/studies/climate-anomalies/)
  does.
- **Derived temperature quantities are converted as absolute temperatures.**
  The diurnal range `*-DUTR-*` and the `*-STDDEV` codes are differences in
  degrees, but `units=metric` applies the full absolute-temperature formula
  `(F - 32) x 5/9`, so they come back negative and wrong. `USW00013967` January
  returned `MLY-DUTR-NORMAL` -5.3, `MLY-TAVG-STDDEV` -16.2, and `MLY-TMAX-STDDEV` -15.8
  under `units=metric` against 22.4, 2.8, and 3.6 under `units=standard`. Read
  these from `units=standard` and scale by `5/9` with no offset: 22.4 F is
  12.4 C, matching the metric `MLY-TMAX-NORMAL` minus `MLY-TMIN-NORMAL` spread.

In the same probe `MLY-TMAX-NORMAL`, `MLY-TMIN-NORMAL`, `MLY-PRCP-NORMAL`,
`DLY-TAVG-NORMAL`, and `ANN-TAVG-NORMAL` did convert: metric temperatures are
degrees Celsius and precipitation is millimeters. Station columns are included
with `includeStationLocation=1`.

Normals are republished about once a decade; the 1991-2020 files can still be
corrected. Retain the cache as well as the manifest and lockfile. See the
[service research notes](noaa-services.md#us-climate-normals) for dated probes.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Resolution, updates, terms, and citation: the [NCEI U.S. Climate Normals product
  page](https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals) and
  the per-period dataset records it links, such as the [annual and seasonal
  record](https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C01619/html),
  whose maintenance frequency is "as needed" and whose use constraint is the Palecki et
  al. (2021) citation. The entry points `terms` at the product page because the
  constraints and DOI differ per period.
- Variables: the [monthly normals
  documentation](https://www.ncei.noaa.gov/data/normals-monthly/1991-2020/doc/Normals_MLY_Documentation_1991-2020.pdf)
  for the data-type codes, with the units this guide's 2026-09-11 probe found, including
  the codes `units=metric` does not convert. The code list is open.
- Latency is empty: normals are 30-year averages, and NCEI publishes no lag for them.

[All NOAA datasets](noaa.md).

--8<-- "generated/catalog/noaa/climate-normals.md"
