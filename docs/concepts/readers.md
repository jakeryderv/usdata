# Readers

A reader opens one cached file into a Python object. Which reader runs is
decided by the asset's media type and id, so restored files open the same way
as freshly fetched ones. Readers live behind optional extras, listed with
their options in the [reader reference](../reference/readers.md).

## What every reader does and does not do

Opening is local. It does not re-fetch, verify checksums, alter the cached
file, update provenance, or write anything. Editing the returned object does
not change its source. Scientific units are not converted, and each source's
own missing-data sentinels are left as the source wrote them, beyond what
pandas and CF decoding normally handle.

Every result carries a copy of the asset id and provenance under a `usdata`
attribute. That is metadata about the source bytes, not a record of your
analysis; see [provenance and drift](provenance-and-drift.md).

Where a file leaves a variable's units missing or `unknown`, the NetCDF4 and
GRIB2 readers fill `units` and `long_name` from the registry entry's variable
table, matching each data variable's name against the entry's names exactly and
then case-insensitively. A decoded MRMS variable drops the product's level
suffix, so `RotationTrackML30min` matches the entry's
`RotationTrackML30min_00.50`. A value the file provides is never overwritten,
no other attribute is touched, and the `registry_attrs` list under the `usdata`
attribute names every variable and attribute filled, so a stamped value stays
distinguishable from the file's own. The CSV readers fill no units, but a Storm
Events frame gains `BEGIN_UTC` and `END_UTC` beside its untouched local columns,
derived from `CZ_TIMEZONE` under the rule listed in `attrs["usdata"]["derived"]`
and described on [the provider page](../providers/noaa-storm-events.md).

Readers are eager. The whole decoded object is in memory when `open()`
returns, and file handles are closed before it does, so there is nothing for
you to manage. The cost is that the decoded size, not the download size, has
to fit.

--8<-- "_snippets/large-grids.md"

## Looking before you open

`item.inspect()` returns a typed summary of a fetched file: where it came from,
how large it is, the format that was recognized, and what that format holds. A
CSV reports its columns and a row count read with the standard library, so it
needs no extra; the count stops after 100,000 rows and says so. A NetCDF4 file
reports its data variables with dims, shape, units, and long name, and a GRIB2
file reports every message with its `shortName`, `name`, `typeOfLevel`, `level`,
`step`, `units`, and grid shape. Those two use the same extras `open()` does,
and a missing one produces a summary whose detail is `None` and whose `note`
names the extra rather than an exception. Bytes that no longer decode are
reported the same way, so a summary of the provenance always comes back.

Inspection reads only the local file and the provenance sidecar beside it.
`usdata.inspect_path(path)` does the same for a cached path without a fetch
result in hand, and `usdata.readers.inventory(path)` returns the GRIB2 message
list on its own. That list is the one the reader's "pass `select`" error prints,
so a multi-message file no longer has to be inventoried by provoking and parsing
an exception.

```sh
usdata inspect ~/.cache/usdata/noaa/hrrr/hrrr.t18z.wrfprsf00.grib2
usdata inspect noaa:hrrr/hrrr.t18z.wrfprsf00.grib2 --json
```

The command takes a cache path or a dataset and asset id, prints the summary
with a table for the detail, and exits 2 when the path has no sidecar or the id
names nothing cached. `--json` emits the summary object and nothing else.

The Python fields are the snake_case spellings of the ecCodes keys the CLI
prints, so `shortName` is `short_name` and `typeOfLevel` is `type_of_level`:

```python
summary = item.inspect()
print(summary.grib2.messages[0].short_name)
```

## CSV and ERDDAP CSV

The pandas extra returns a DataFrame. Identifier-like columns default to
string dtype so leading zeros survive; the reference lists which names, and an
explicit `dtype` overrides the default. Dates are not parsed unless you ask.
An ERDDAP response has a second row of units, which the `erddap-csv` reader
consumes into `frame.attrs["units"]`; USGS per-observation units stay as
ordinary columns. A gzipped CSV is decompressed through a stream, never into
the cache. `nrows` limits parsing and does not check the whole archive; use
`verify` for integrity.

```python
frame = items[0].open(parse_dates=["time"], usecols=["time", "analysed_sst"])
print(frame["analysed_sst"].mean(), frame.attrs["units"]["analysed_sst"])
```

For parser options beyond the small set usdata exposes, call pandas on
`item.path` yourself and account for the ERDDAP units row.

## NEXRAD Level II

The radar extra returns an xarray DataTree decoded by xradar, one `sweep_N`
child per sweep with native fields, coordinates, and units. Whole-file gzip
and bzip2 and internal Archive II compression are handled. Passing `sweep=0`
or `sweep=[0, 2]` limits decoding to those sweeps; the entire archived file is
still downloaded and inspected, and the child names keep their original
indices.

Before decoding, the reader checks that moment and coordinate records align.
An interior sweep missing its end marker can shift the decoder's coordinate
table and pair observations with the wrong coordinates, so such a request
raises `RadarDecodeError` rather than returning a partial result. Select an
unaffected sweep explicitly. The KTLX volume `KTLX20240507_044053_V06`, which the
event-context and tornado-classification examples use, is the known case: its
first sweep opens and full-volume decoding does not. The guard does not repair
the file or certify its
quality.

Reserved codes become NaN, incomplete sweeps with aligned metadata are padded
with NaN so received rays stay available, and xradar's warnings about angle
reconstruction are preserved. No rainfall conversion, clutter removal, or
velocity unfolding is performed. Legacy files may lack location metadata,
which the reader does not guess.

```python
radar = item.open(sweep=0)
sweep = radar["sweep_0"].to_dataset()
print(sweep["DBZH"].attrs["units"])
```

## NetCDF4 scenes

The netcdf extra returns an xarray Dataset of the file's root group. CF packed
values, unsigned storage, fill values, and time coordinates are decoded;
dimensions, units, projection metadata, and data-quality flags are retained.
Quality filtering and projection are yours to do. Classic NetCDF3, arbitrary
HDF5, nested groups, and lazy opening are not supported; use xarray on
`item.path` for those.

## GRIB2 fields

The grib extra decodes through the ecCodes bindings and returns an xarray
Dataset with one float32 variable per selected message on one shared grid.
Regular latitude-longitude grids get one-dimensional coordinates computed from
the grid definition; projected grids such as HRRR's Lambert conformal get
two-dimensional `latitude` and `longitude` on `y` and `x`, with the projection
parameters as attributes. Rows run north to south and columns west to east
whatever the file's scanning mode, and longitudes keep the file's convention,
0 to 360 degrees for NOAA products.

A file with one message opens directly. A file with several needs `select`, a
mapping of ecCodes key names to a value or list of values; without it the
reader raises a `ValueError` listing every `(shortName, typeOfLevel, level)`
rather than loading hundreds of fields. Strings match a key's text form and
numbers its numeric form. Variables are named by `shortName` when every
selected message shares one `typeOfLevel` and level, and by
`shortName_typeOfLevel_level` for all of them as soon as the selection spans
more than one, so a select always returns the same names whatever else the file
holds. `attrs["usdata"]["messages"]` maps each variable name back to the message
it came from: its index in the file, `shortName`, `typeOfLevel`, `level`, and
`step`. ecCodes has no names for MRMS parameters, so those take the product from
the file name, for example `RotationTrackML30min`, which the registry's
`RotationTrackML30min_00.50` entry then supplies the units for. Values marked
missing by a bitmap become NaN; product sentinels such as MRMS `-999` and `-99`
are kept because their meaning belongs to the product. Gzipped files are
decompressed in memory.

A select value that matches none of the selected messages is reported: by
default the reader warns and returns the fields it did find, and `strict=True`
raises instead, which is the safe setting for a script whose field list must be
complete. HRRR carries `hlcy` only in layers above ground, so both level types
have to be named for both fields to arrive.

```python
env = item.open(
    select={"shortName": ["cape", "hlcy"], "typeOfLevel": ["surface", "heightAboveGroundLayer"]},
    strict=True,
)
print(list(env.data_vars), env["cape_surface_0"].attrs["units"])
```

Lazy opening, regridding, reprojection, spatial subsetting, and GRIB1 are not
supported. The backend choice is recorded in
[ADR 0022](https://github.com/jakeryderv/usdata/blob/main/docs/adr/0022-grib2-reader-backend.md).

## HURDAT2 best tracks

The pandas extra parses the fixed-format text into one row per track point,
with storm id and name repeated on every row so the table groups naturally.
Documented sentinels become NaN, numeric columns are float with units in their
names, blank identifiers are missing rather than empty strings, and longitudes
are normalized into -180 to 180 because some revisions carry a track past the
prime meridian in an unwrapped convention. A malformed line, count, or value
raises `Hurdat2FormatError` naming the line instead of returning a partial
table. Archived revisions read the same as current ones; the radius of maximum
wind, added for the 2021 season, is NaN where a revision lacks it.

```python
tracks = item.open()
landfalls = tracks[tracks.record_identifier == "L"]
```

## Formats without a reader

NEXRAD Level III products are fetched whole and `open()` raises
`UnsupportedFormat` naming `item.path`; Py-ART's `read_nexrad_level3` decodes
them. Geospatial formats have no reader yet. Everything else usdata does,
including fetch, pull, verify, and provenance, works without any extra.
