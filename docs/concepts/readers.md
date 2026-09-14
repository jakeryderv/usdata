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

Readers are eager. The whole decoded object is in memory when `open()`
returns, and file handles are closed before it does, so there is nothing for
you to manage. The cost is that the decoded size, not the download size, has
to fit.

--8<-- "_snippets/large-grids.md"

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
unaffected sweep explicitly. The guard does not repair the file or certify its
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
numbers its numeric form. Variables are named by `shortName`, with level type
and value appended when several selected messages share one. ecCodes has no
names for MRMS parameters, so those take the product from the file name, for
example `RotationTrackML30min`. Values marked missing by a bitmap become NaN;
product sentinels such as MRMS `-999` and `-99` are kept because their meaning
belongs to the product. Gzipped files are decompressed in memory.

```python
env = item.open(select={"shortName": ["cape", "hlcy"], "typeOfLevel": "surface"})
print(list(env.data_vars), env.cape.attrs["units"])
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
