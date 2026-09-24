# IBTrACS global best tracks

Available since v0.20.0 as `noaa:ibtracs`. The International Best Track
Archive for Climate Stewardship merges every agency's tropical cyclone best
tracks, from the NHC and JTWC to Tokyo, New Delhi, Réunion, and the Southern
Hemisphere centres, into one global record since 1842, and NCEI publishes it
as whole files under an anonymous HTTPS directory. There is no query
interface: no records API, no per-storm files in the current version, no
server-side subsetting. Like [HURDAT2](noaa-hurdat2.md), the asset is one
whole file, and the value lives in the reader and in choosing the right file.

## Selecting a file

`subset` is required and names one of the eleven files NCEI builds, matched
case-insensitively:

| `subset` | Holds | CSV size on 2026-09-17 |
|---|---|---|
| `all` | The complete record, every basin | 332 MB |
| `since1980` | Every storm from the 1980 season on | 144 MB |
| `last3years` | The current season and the three before it | 10 MB |
| `active` | Storms active at the build | 122 KB |
| `na`, `ep`, `wp`, `ni`, `si`, `sp`, `sa` | One basin: North Atlantic, eastern North Pacific, western North Pacific, North Indian, South Indian, South Pacific, South Atlantic | 56 KB (`sa`) to 114 MB (`wp`) |

A basin file holds every storm that ever entered the basin, whole, so the
North Atlantic file also carries the `EP` and `NI` points of storms that
crossed over. `format` is `csv` (the default) or `netcdf`; the NetCDF file
holds the same fields as `storm` by `date_time` arrays, under a tenth the size
for the large subsets and larger than the CSV for the smallest, since every
storm gets the same 360 time slots. Shapefiles are published too but not offered, since no
reader opens them. `version` pins a product version directory such as
`v04r00`; by default the adapter lists the archive root and takes the newest.
Versions before v4 publish one NetCDF file per storm in a different layout and
are refused.

Any other parameter, a location or bbox, `variables`, and text queries are
rejected with an error rather than silently ignored, because none of them can
change which bytes are downloaded. **Dates are rejected too**: every file
holds the complete record for its subset, so a `start`/`end` pair would select
nothing. Choose `since1980` or `last3years` when a period is what you want,
and filter the parsed `ISO_TIME` column locally. `capabilities` are all false.

Asset time bounds report the subset's definition, not its first and last
record: `since1980` starts on 1980-01-01, `last3years` on 1 January three years
before the build, and the others at the archive's first record,
1842-10-25T03:00Z. The end is the file's build stamp from the directory
listing, read as UTC (it matched the `Last-Modified` header on 2026-09-17),
which every record in the file necessarily precedes. Should a listing ever
omit the stamp, the end is left open and `last3years` falls back to the
archive start.

## Builds, versions, and lockfiles

IBTrACS differs from HURDAT2 in how it revises. A product version (`v04r01`
since 2024) is a directory that stays; inside it, NCEI rebuilds every file in
place, under the same name, whenever an agency delivers tracks, which the
[change log](https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/doc/IBTrACS_v04r01_change_log.txt)
shows happening most months and the build stamps show happening most days.
Superseded builds are not kept upstream: the `archive/` directory holds only
the current build's tarballs.

So a lockfile's checksum is what pins the bytes. A repeat `usdata pull` from a
lockfile downloads the pinned URL, finds different bytes, and stops with an
upstream-change error rather than quietly replacing the data. Pass
`--update noaa:ibtracs` to accept the current build, or `--force` to
re-resolve, which also moves to a newer product version once NCEI publishes
one. A plain `fetch` without a lockfile also notices a rebuild: the listing
reports the new file's size, and a cached copy of another size is fetched
again rather than served stale. A build that has been superseded cannot be fetched again from NCEI, so
keep the cache with the manifest and lockfile; a pinned example restores from
the [mirror](../concepts/provenance-and-drift.md#restoring-from-a-mirror)
instead. The complete filename is the stable asset ID, and the URL, original
bytes, exact listed size, and checksum are preserved.

--8<-- "_snippets/upstream-revisions.md"

## Opening the file

The CSV lays a units row under its header, as ERDDAP responses do, so
`FetchedAsset.open()` selects the `erddap-csv` reader for `noaa:ibtracs` CSV
assets and keeps the units in `frame.attrs["units"]` (`kts`, `mb`, `nmile`,
`degrees_north`; an empty string for text columns). Two conventions in the
file would otherwise mislead pandas, and the reader handles both: a missing
value is written as a single space, which is read as missing so that
measurement columns are numeric; and the North Atlantic basin code is the
literal `NA`, which pandas would read as missing by default and which here
stays text. The generic CSV options apply: `parse_dates=["ISO_TIME"]` parses
the naive UTC timestamps, and `usecols` trims the 174 columns.

The columns are: the storm's serial id, season, number, basin, sub-basin, and
name; `ISO_TIME`, `NATURE`, position, and the responsible WMO agency's wind,
pressure, and name; `TRACK_TYPE`, distance to land, landfall flag, and the
per-agency interpolation flags; then each agency's own report in its own
columns. The U.S. set (`USA_LAT`, `USA_LON`, `USA_WIND`, `USA_PRES`,
`USA_SSHS`, `USA_STATUS`, `USA_RECORD`, the 34, 50, and 64 kt wind radii by
quadrant, `USA_RMW`) is the most complete and is the one the catalog entry
describes; Tokyo, CMA, HKO, KMA, New Delhi, Réunion, BOM, Nadi, Wellington,
DS824, TD9636, TD9635, Neumann, and MLC follow, then gusts and sea-height
radii, and `STORM_SPEED` and `STORM_DIR` close the row. NCEI's
[column documentation](https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/doc/IBTrACS_v04r01_column_documentation.pdf)
defines each.

`format: netcdf` opens with the `netcdf` reader as an xarray Dataset of
`storm` by `date_time` arrays, with a `quadrant` axis for the wind radii, the
same lower-case variable names, and units the file states itself. Opening is
local either way: it never re-fetches or changes provenance, which is copied
into `attrs["usdata"]`.

## Scientific limits

IBTrACS is a merge, not a reanalysis. Each agency's values are reported in
that agency's own columns and conventions: the U.S. agencies give 1-minute
sustained winds, most others 10-minute means, so `USA_WIND` and `TOKYO_WIND`
are not comparable for the same storm, and `WMO_WIND` switches agency and
averaging period as a storm moves between areas of responsibility. Positions
are interpolated to three hours between the agencies' six-hourly points, and
`IFLAG` says which values are original.

Read `TRACK_TYPE` before comparing seasons. A storm is `main` once its
responsible agency has delivered a post-season best track; until then it is a
`PROVISIONAL` or `US-PROVISIONAL` operational track, which the agency revises.
In the file built on 2026-09-17, every 2023 and 2024 storm was `main`, 46 of
115 2025 storms were, and no 2026 storm was. Coverage before the satellite era
is uneven across basins in the same ways as HURDAT2, and worse where no
aircraft reconnaissance flew: counting storms per decade in the Indian Ocean
measures observing systems more than climate. A Southern Hemisphere `SEASON`
is the year it ends in: the 2025 South Indian season runs from late 2024.

The [manifest example](https://usdata.dev/datasets/noaa/ibtracs/) pulls the
`last3years` file and ranks the strongest recent storms with the provisional
tracks labelled. See the [service research notes](noaa-services.md#ibtracs-global-best-tracks)
for dated upstream probes.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Resolution and variables: the files' own attributes (`geospatial_lat_resolution`
  0.10, `time_coverage_start` 1842-10-25T03:00) and the
  [column documentation](https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/doc/IBTrACS_v04r01_column_documentation.pdf),
  with the three-hourly cadence measured in the North Atlantic file.
- Updates: the
  [v04r01 change log](https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/doc/IBTrACS_v04r01_change_log.txt)
  and the build stamps in the directory listings.
- Citation and terms: the [product page](https://www.ncei.noaa.gov/products/international-best-track-archive),
  which asks that the v04r01 dataset (Gahtan et al. 2024, doi:10.25921/82ty-9e16) and
  Knapp et al. (2010) be cited, and the files' `license` attribute, "These data may be
  redistributed and used without restriction."
- Latency is empty: agencies deliver best tracks on their own schedules, from weeks to
  more than a year after a season.

[All NOAA datasets](noaa.md).

--8<-- "generated/catalog/noaa/ibtracs.md"
