# Find a dataset

Search ranks the curated registry by keyword and can filter by provider,
place, and time. `usdata datasets` lists the same registry without a keyword.
Both run offline and never query an agency catalog, so anything they return as
**available** can be fetched.

```console
$ usdata search precipitation --location "Cleveland County, OK"
noaa:ghcn-daily       available  since 0.2     GHCN-Daily Station Observations
noaa:climate-normals  available  since 0.11    U.S. Climate Normals 1991-2020
noaa:gsom             available  since 0.7     Global Summary of the Month
noaa:lcd              available  since 0.14    Local Climatological Data
noaa:nexrad-level2    available  since 0.2     NEXRAD Level II Radar
noaa:mrms             available  since 0.15    Multi-Radar Multi-Sensor (MRMS)
$ usdata info noaa:mrms
```

## List and filter without a search term

`usdata datasets` prints the whole registry as a table of id, status with the
version it shipped in, domain, delivered formats, the reader extra that opens
the files, and a one-line summary. Every filter narrows the list, and they
combine:

```console
$ usdata datasets --domain severe-weather
noaa:storm-events         available (since 0.8)   severe-weather  gzip CSV  pandas  Storm Events details
noaa:spc-tornado-reports  available (since 0.15)  severe-weather  CSV       pandas  SPC tornado database
$ usdata datasets --format grib2 --capability temporal_subset
noaa:mrms  available (since 0.15)  weather-radar   GRIB2 (gzipped)  grib  MRMS gridded radar products
noaa:hrrr  available (since 0.15)  weather-models  GRIB2            grib  HRRR model output
noaa:gfs   available (since 0.15)  weather-models  GRIB2            grib  GFS model output
```

`--provider` and `--domain` take an id. `--format` matches case-insensitively
anywhere in a declared format, so `csv` also finds `gzip CSV`. `--reader` takes
a reader extra or `none` for datasets that arrive as bytes with no reader.
`--capability` takes `spatial_subset`, `temporal_subset`, or `variable_subset`
and keeps the datasets that declare it. `--status` is `available` (the default),
`planned`, or `all`.

`usdata search` accepts the same six options on top of its keywords, place, and
time, and both commands accept `--json`, which prints the matching registry
entries as a JSON array and nothing else. Search records carry their `score`.

```console
$ usdata datasets --reader pandas --provider usgs --json | jq -r '.[].id'
usgs:water-daily
```

Both commands exit 1 when nothing matches, so a shell script can tell an empty
result from a bad option, which exits 2. Search text with no letters or digits,
such as `?`, is a bad option too: it has no keyword to match.

`info` prints a dataset's status, domain, license, extent, capabilities, and
every provider parameter it accepts with a one-line description. That list is
read from the adapter, so it is always current.

The [dataset grid](https://usdata.dev/datasets/) shows the same registry with
search and agency and topic filters. Each dataset there has a page with a
preview, a quick start, and a walkthrough notebook. Here in the docs, each
dataset has one page, listed in the [dataset reference](../generated/catalog/index.md):
how to select it, what arrives, where the quirks live (window limits,
local-time columns, sentinel values, and how the source revises), and its
generated reference of parameters, variables, and catalog facts at the end.

Three things to read before fetching a dataset for the first time:

- **Selection rule.** A station query returns observations inside the window;
  Storm Events returns whole annual files; radar and satellite datasets return
  whole files whose start falls inside the window. The catalog's selection
  column says which.
- **Required inputs.** Some datasets need a station or site id, some need a
  satellite or product name, and some reject geographic selection entirely.
- **Maximum window.** Files that arrive every two minutes have one-day limits
  for a reason; use `--dry-run` to see the count and size before downloading.

--8<-- "_snippets/planned-datasets.md"

The [SPC tornadoes example](https://usdata.dev/datasets/noaa/spc-tornado-reports/) is a
one-file dataset with no parameters; the
[MRMS rotation example](https://usdata.dev/datasets/noaa/mrms/) shows a
product parameter and a tight window.
