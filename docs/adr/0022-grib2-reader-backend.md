# 0022: GRIB2 reading through ecCodes, built into xarray by usdata

Status: accepted. Date: 2026-09-14. Updated by [ADR 0042](0042-one-open-method-per-format.md).

## Context

MRMS gridded radar products, HRRR, and GFS all ship GRIB2. None of them is
useful without a local reader, and the reader's backend decides the
dependency footprint of a new extra and which platforms can install it with
pip alone. Three candidates were tried on 2026-09-14 against one MRMS
`RotationTrackML30min` file (0.005°, 7000 × 14000 points, PNG packing), six
further MRMS products at both grid sizes, and one 150 MB HRRR surface file
(170 messages, Lambert conformal, complex packing with spatial differencing).

**ecCodes** (`eccodes` on PyPI, 2.48) decoded every file. Values for the
98-million-point rotation grid took 0.57 s; a full 170-message HRRR header scan
took 0.40 s and one field with its 2-D latitudes and longitudes 0.22 s. ecCodes
does not know MRMS parameter names (discipline 209 uses local tables), so
`shortName` is `unknown` for every MRMS message; the discipline, category, and
parameter numbers are exposed and correct. Its `distinctLatitudes` key took
11 s on the rotation grid, but regular grids reconstruct identical coordinates
from the first point and increments in milliseconds. PNG-packed data cannot be
unpacked through the float32 API, so values arrive as float64 and are cast.
Linux wheels for every supported Python come through `eccodeslib`; Windows
wheels bundle the library for CPython 3.9 through 3.13; macOS has no wheel and
needs the library from conda-forge or Homebrew, which `findlibs` locates.

**gribberish** (1.7, Rust) decoded HRRR fields in 0.06 s each and the 0.01°
MRMS products with correct MRMS names and units, but panicked with
`range end index 98000001 out of range for slice of length 98000000` on every
0.005° grid tried: `RotationTrack30min`, `RotationTrackML30min`, and
`RotationTrackML60min`, the products this workstream exists for. It rejected the
three-dimensional `MergedReflectivityQC` product as unsupported, returned
`missing` for EchoTop and VIL names, and its current API requires Python 3.12;
on 3.11 pip resolves to 0.30 with a different API. No upstream issue records the
panic. It ships wheels for every platform.

**pygrib** (2.1.8) bundles ecCodes in Linux and macOS wheels for CPython 3.10
through 3.14 but has no Windows wheel and exposes its own message objects
rather than arrays with coordinates.

**cfgrib** wraps ecCodes into xarray and was tried first. Opening the rotation
file took 19 s, almost all of it computing coordinates through
`distinctLatitudes`, and its hypercube merging requires `filter_by_keys` for
multi-message files and fails when messages do not align. It adds an index-file
side effect beside the data unless disabled.

## Decision

Add a `grib` extra that installs `eccodes`, `xarray`, and `numpy`. Add
`reader="grib2"`, inferred from GRIB2 media types, implemented in
`usdata._grib` directly on the ecCodes Python bindings without cfgrib. The
reader builds an xarray Dataset itself: one data variable per selected message,
named from `shortName` when ecCodes knows it and otherwise from the asset's
product (MRMS keys carry the product name), with `units`, `typeOfLevel`,
`level`, discipline, category and parameter numbers, packing type, reference
and validity times, and step as attributes. Regular latitude-longitude grids get
1-D coordinates computed from the first point and increments; projected grids
get 2-D `latitude` and `longitude` from ecCodes plus the projection parameters
as attributes. Values are float64 from ecCodes, cast to float32, with the
message's missing value masked to NaN. Dataset attributes carry the asset id
and provenance under `usdata`, matching the other readers.

Selection is explicit. `open(select={...})` takes ecCodes key names mapped to
one value or a list of values, for example
`select={"shortName": "cape", "typeOfLevel": "surface"}`. A file with one
message needs no selection. A multi-message file opened without `select`
raises a `ValueError` listing the available `(shortName, typeOfLevel, level)`
triples rather than loading hundreds of fields. Gzipped GRIB2, which is how
MRMS is published, is decompressed in memory without changing cached bytes,
following the Storm Events rule. CSV options and `sweep` are rejected for this
reader as they are for NetCDF.

The extra is supported with pip alone on Linux for every Python the project
supports and on Windows for CPython 3.13 and earlier. macOS and Windows 3.14
users install the ecCodes library separately; the reader reports a missing
library with the install hint rather than failing inside ecCodes. CI adds a
`grib` profile to the Linux readers matrix on 3.11 and 3.14; the built-wheel
smoke jobs do not install the extra, since two of the four smoke platforms
cannot.

## Consequences

One decoded MRMS rotation grid needs about 1.2 GB at peak, 784 MB of float64
from ecCodes plus the float32 copy, before the float64 array is released.
The reader documents this and callers who need less should select coarser
products or use `fetched.path` with a chunked backend. The reader is eager,
like NetCDF, and excludes lazy or dask-backed opening, regridding,
reprojection, spatial subsetting, and GRIB1.

gribberish remains attractive for its wheels and speed. If a release fixes the
0.005° panic and the 3.11 floor becomes moot, a backend swap would change only
`usdata._grib`; the reader interface above does not expose ecCodes objects.

## Validation

A synthetic GRIB2 fixture written with ecCodes covers regular and Lambert
grids, missing values, gzip, selection, the no-selection error, and file
closure. The live MRMS and HRRR tests open real files through the reader.
