# CPC ENSO indices

Available since v0.33 as `noaa:enso-indices`. The Climate Prediction Center
publishes its seasonal El Niño-Southern Oscillation indices as plain-text
tables, each holding the whole record from DJF 1950. Access is anonymous
HTTPS, and one query fetches one table:

```sh
uv run usdata fetch noaa:enso-indices --dry-run              # RONI, the default
uv run usdata fetch noaa:enso-indices -p index=oni --dry-run
```

## Which index

| `index` | File | Columns | What it is |
|---|---|---|---|
| `roni` (default) | `RONI.ascii.txt` | `SEAS YR ANOM` | Relative Oceanic Niño Index, NOAA's official ENSO index since 1 February 2026 |
| `oni` | `oni.ascii.txt` | `SEAS YR TOTAL ANOM` | Oceanic Niño Index, the traditional index |

Both are three-month running means of the Niño 3.4 region's sea surface
temperature anomaly, 5°N to 5°S and 170°W to 120°W, computed from ERSST v6
([`noaa:ersst`](noaa-ersst.md)). They differ in what the anomaly is measured
against:

- **ONI** uses 30-year base periods centred on each era and updated every five
  years. `TOTAL` is the season's mean temperature, and `ANOM` its anomaly.
- **RONI** uses the 1991-2020 base, subtracts the mean anomaly of the whole
  tropics (20°N to 20°S) from the Niño 3.4 anomaly, and rescales the
  difference to the traditional index's variance, as
  [NWS Public Information Statement 26-05](https://www.weather.gov/media/notification/pdf_2026/pns26-05_Relative_ONI.pdf)
  sets out.

An El Niño is five or more consecutive overlapping seasons at +0.5 °C or
above; a La Niña, at −0.5 °C or below. When the tropics as a whole are warm,
the two indices part: JJA 2026 is ONI +1.80 and RONI +1.36 (checked
2026-09-28).

## Rows and seasons

Each row is one overlapping season named by its three initials. `YR` is the
year of the middle month, so `DJF 1950` is December 1949 to February 1950 and
`NDJ 1950` is November 1950 to January 1951. The first row is DJF 1950, and the
asset's time starts on 1 December 1949 and is open-ended.

The table is the whole record, so there is nothing to select on the server: a
window, a box, variables, and text are refused, and only `index` is accepted.
Every capability is false. Listing makes no request and reports no size; each
file is under 25 kB.

## Reading a table

There is no bundled reader: the files are whitespace-delimited text, not CSV,
and `open()` refuses them. pandas reads them in one line:

```python
import pandas as pd

roni = pd.read_csv(item.path, sep=r"\s+")
```

## Revisions

CPC rewrites both files in place each month, by the fifth, when it adds the
newest season. Its RONI page adds that "RONI values may change up to two months
after the initial 'real time' value is posted", because of the filtering in
ERSST v6, and ONI's base periods move every five years. A lockfile pins the
table as it was. The next month's rewrite shows as a changed entry, and a
restore then needs the cached copy or the mirror.

--8<-- "_snippets/upstream-revisions.md"

Legacy tables computed from ERSST v5 are still on the same server,
`RONI.v5.ascii.txt` and `ersst5.nino.mth.91-20.ascii`, but this dataset does
not serve them.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Definitions, resolution, and update cadence: CPC's
  [RONI page](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/)
  ("updated by the 5th of each month") and
  [ONI page](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/),
  and NWS Public Information Statement 26-05.
- Variables: the header rows of the two files.
- Terms: CPC's pages link the [NWS disclaimer](https://www.weather.gov/disclaimer).
  CPC publishes no citation form, so the entry uses the agency, product, and
  access form.
- Latency is empty: CPC gives a publication day, not a lag. The JJA 2026 season
  was in both files on 2026-09-03.

[All NOAA datasets](noaa.md).

--8<-- "generated/catalog/noaa/enso-indices.md"
