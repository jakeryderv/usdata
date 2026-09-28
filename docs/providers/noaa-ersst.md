# ERSST v6 monthly sea surface temperature

Available since v0.33 as `noaa:ersst`. The Extended Reconstructed Sea Surface
Temperature is NCEI's monthly global analysis of sea surface temperature on a
2 degree grid, reconstructed from ship, buoy, and Argo observations back to
January 1850. It is the record behind ENSO indices such as the Oceanic Niño
Index. Access is anonymous HTTPS, one NetCDF4 file per month:

```sh
uv run usdata fetch noaa:ersst --start 2026-06-01 --end 2026-08-31 --dry-run
```

```text
ersst.v6.202606.nc	168286	https://www.ncei.noaa.gov/data/sea-surface-temperature-extended-reconstructed/v6/access/ersst.v6.202606.nc
ersst.v6.202607.nc	168286	https://www.ncei.noaa.gov/data/sea-surface-temperature-extended-reconstructed/v6/access/ersst.v6.202607.nc
ersst.v6.202608.nc	168286	https://www.ncei.noaa.gov/data/sea-surface-temperature-extended-reconstructed/v6/access/ersst.v6.202608.nc
3 asset(s) matched, 504858 bytes
```

## Selection

Both dates are required and read in UTC. Every calendar month the window
touches is returned whole, so `2026-06-15` to `2026-07-01` selects June and
July. A window starting before January 1850 is an error, as is one reaching a
month NCEI has not published; the error names the newest published month. The
files are global grids with no server-side subsetting, so location, bbox,
variables, and text are refused and there are no parameters: crop and select
after opening. Only `temporal_subset` is true.

The asset id is NCEI's filename, `ersst.v6.YYYYMM.nc`, and the asset's time is
the whole calendar month. The file's own `time` coordinate is the middle of the
month, `2026-08-15`, as NCEI stamps it.

## What a file holds

One `time × lev × lat × lon` grid of `1 × 1 × 89 × 180`: latitudes from 88°S to
88°N and longitudes from 0 to 358°E, every 2 degrees, at grid centres. Two
variables, both `degree_C` as float32:

- `sst`: the reconstructed monthly mean sea surface temperature.
- `ssta`: its anomaly from the 1991-2020 ERSSTv6 climatology, the base period
  CPC's current ENSO indices use.

Land and sea ice are missing values. `open()` uses the netcdf extra and returns
a loaded xarray Dataset:

```python
grid = item.open()
nino34 = grid.ssta.sel(lat=slice(-5, 5), lon=slice(190, 240)).mean()
```

That box, 5°S to 5°N and 170°W to 120°W, is the Niño 3.4 region. Longitudes run
0 to 360, so 170°W is 190.

## Versions and revisions

Checked on 2026-09-28. The product page describes version 6, released in
December 2025, which replaces v5's empirical orthogonal teleconnections with an
artificial neural network. v6 is the only version this adapter reads.

- v6 is NetCDF4 for every month from 1850. v5's official directory stops at
  February 2026, and its files before 2008 are classic NetCDF3 on a 360-day
  calendar.
- CPC computes its ENSO indices from v6: the traditional Oceanic Niño Index,
  on 30-year base periods centred on each era and updated every five years,
  and the Relative Oceanic Niño Index (RONI), which NOAA has used officially
  since 1 February 2026 (NWS Public Information Statement 26-05). RONI first
  subtracts the 20°N-20°S tropical mean anomaly. A Niño 3.4 mean of `ssta`,
  on its one fixed 1991-2020 base, is within 0.1 °C of ONI for recent seasons:
  JJA 2026 is 1.78 against ONI 1.80. RONI for that season is 1.36.

The directory listing shows how files are revised. Months from 1850 through 2007
were written on 2025-05-02, and 2008 through January 2026 were rewritten once on
2026-04-03. Since then, each monthly update, around the third, writes the month
just ended and rewrites the month before it: July and August 2026 both carry
2026-09-03 and June 2026-08-03. **The newest month is preliminary**, so a
lockfile that pins it reports that entry as changed after the next update, and
`usdata verify --listing` shows it. Older months have not changed since they
were rewritten.

--8<-- "_snippets/upstream-revisions.md"

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Resolution, variables, and climatology: each file's global attributes
  (`spatial_resolution`, `time_coverage_resolution`, `climatology`) and its
  variable attributes.
- Updates: the [v6 directory
  listing](https://www.ncei.noaa.gov/data/sea-surface-temperature-extended-reconstructed/v6/access/)
  and its modified stamps, read on 2026-09-28; NCEI states no cadence in words.
- Citation: the [product page](https://www.ncei.noaa.gov/products/extended-reconstructed-sst),
  which cites the two 2025 Journal of Climate papers and says a data DOI for v6
  is still to be issued. The entry cites Part I.
- Terms: each file's `license` attribute says "No constraints on data access
  or use". NCEI publishes no metadata record for the v6 collection
  (`gov.noaa.ncei:C01737` returned 404 on 2026-09-28), so the entry links the
  product page.
- Latency is empty: the product page does not say how far behind the present
  the files run. The August 2026 file appeared on 2026-09-03.

[All NOAA datasets](noaa.md).

--8<-- "generated/catalog/noaa/ersst.md"
