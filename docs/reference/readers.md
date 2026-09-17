# Reader options

How each reader behaves is explained in [readers](../concepts/readers.md).
This page lists what to install, what is inferred, and what `open()` accepts.

## Readers and extras

| Reader | Extra | Returns | Inferred for |
|---|---|---|---|
| `csv` | `pandas` | pandas DataFrame | `text/csv`, `application/csv` (charset parameters allowed); `application/gzip` or `application/x-gzip` when the id ends in `.csv.gz` |
| `erddap-csv` | `pandas` | pandas DataFrame with `attrs["units"]` | CSV media types on an asset whose protocol is ERDDAP |
| `hurdat2` | `pandas` | pandas DataFrame, one row per track point | `noaa:hurdat2` assets, or ids `hurdat2-*.txt` |
| `nexrad-level2` | `radar` | xarray DataTree | `noaa:nexrad-level2` assets |
| `netcdf` | `netcdf` | xarray Dataset | `application/x-netcdf`, `application/netcdf`, `application/x-netcdf4` |
| `grib2` | `grib` | xarray Dataset | `application/x-grib2`, `application/grib2`, `application/x-grib`, `application/wmo-grib2`; ids ending `.grib2`, `.grb2`, or their `.gz` forms when the media type is missing, generic, or gzip |

`noaa:nexrad-level3` assets have no reader and `open()` raises
`UnsupportedFormat`. Install extras as `pip install "usdata[pandas,grib]"`; the
[Install](../install.md) page has the platform notes for `grib`.

## Options

| Option | Applies to | Behavior |
|---|---|---|
| `reader` | all | Overrides inference: `"csv"`, `"erddap-csv"`, `"hurdat2"`, `"nexrad-level2"`, `"netcdf"`, or `"grib2"`. Use it for ambiguous media metadata. |
| `dtype` | CSV readers | Mapping of column names to pandas dtype strings; overrides the identifier defaults below. |
| `parse_dates` | CSV readers | Columns to parse as dates. Nothing is parsed by default; `dtype={"DATE": "string"}` keeps numeric-looking labels as text. |
| `usecols` | CSV readers | Columns to read, in pandas order. |
| `nrows` | CSV readers | Maximum observation rows, excluding header and units rows. |
| `sweep` | `nexrad-level2` | Zero-based integer or non-empty list of distinct integers; `None` opens every sweep. |
| `select` | `grib2` | Mapping of ecCodes key names to one value or a list of values; required when a file holds more than one message. |
| `strict` | `grib2` | `True` raises when a `select` value matches none of the selected messages; the default warns and returns the rest. |

Passing an option to a reader it does not apply to raises `ValueError`, even
with an empty value.

## GRIB2 variable names

Variables are named by `shortName` when every selected message shares one
`typeOfLevel` and level, and by `shortName_typeOfLevel_level` for all of them
as soon as the selection spans more than one, so the names follow from the
select rather than from which short names happened to repeat.

## GRIB2 message numbering

A message carries two numbers, and they are not the same. `file_index` is its
zero-based position in the local file, which is what `usdata inspect` prints
and what `readers.inventory` counts. `object_index` is the one-based number the
source object's `.idx` sidecar gave it, so it survives only where a
[partial fetch](../concepts/provenance-and-drift.md#files-fetched-as-byte-ranges)
recorded which messages it took; it is `None` for a whole file. Both appear on
`GribMessage` and in `attrs["usdata"]["messages"]`, and `usdata inspect` prints
the `object #` column only when the file has one.

A GRIB2 message can hold several fields; RAP packs wind components that way,
and its index numbers them `12.1` and `12.2`. The reader opens every field
(ecCodes multi-field support is switched on for the process when the reader
loads), and the fields of one message share its `file_index`, `object_index`,
and `selector`. A gzip-compressed file, which is how MRMS arrives, is read one
field per message.

## GRIB2 selectors and variable names

A partial fetch also records the index `selector` each message was fetched for,
which `usdata inspect` prints in a `selector` column and the reader puts on each
`messages` entry. `Grib2Summary.variable_for(selector)` turns one of those
selectors into the variable name the naming rule above gives that message, so a
notebook that asked for `CAPE:surface` can look up the `cape_surface_0` it became
instead of guessing it; a selector this file holds no message for raises
`KeyError` naming the ones it does.

## CSV identifier defaults

These column names, matched case-insensitively, default to pandas string dtype
so leading zeros survive: `STATION`, `station_id`, `site_no`,
`monitoring_location_id`, `parameter_code`, `statistic_id`, `event_id`,
`episode_id`, `state_fips`, `cz_fips`, `tor_other_cz_fips`. No padding is
added; other numeric-looking ids need an explicit `dtype`. Other columns use
pandas inference and default missing-value parsing.

## Result attributes

| Reader | Where | Contents |
|---|---|---|
| CSV readers | `frame.attrs["usdata"]` | Asset id and a JSON-compatible copy of its provenance |
| `erddap-csv` | `frame.attrs["units"]` | Units row, filtered to the selected columns |
| `nexrad-level2` | `radar.attrs["usdata"]` | Asset id, provenance, and `sweeps` listing the returned groups |
| `netcdf`, `grib2` | `dataset.attrs["usdata"]` | Asset id and provenance |
| `grib2` | `dataset.attrs["usdata"]["messages"]` | Each variable name mapped to its message's `file_index`, `object_index`, `shortName`, `typeOfLevel`, `level`, and `step`, plus the `selector` a partial fetch asked for |
| `grib2` | per-variable `attrs` | `units`, `name`, `typeOfLevel`, `level`, discipline, category, and parameter numbers, packing type, reference and valid times, step; projection parameters on the Dataset for projected grids |

## Errors

| Error | From `usdata.readers` | Raised when |
|---|---|---|
| `MissingReaderDependency` | subclass of `ImportError` | The extra is not installed; the message names it, and for `grib` also names the ecCodes library when the binding is present but the library is not |
| `UnsupportedFormat` | subclass of `ValueError` | No reader matches, an unknown `reader` name is passed, or the asset is a Level III product |
| `RadarDecodeError` | subclass of `ValueError` | Moment and coordinate records do not align for the requested sweeps |
| `Hurdat2FormatError` | subclass of `ValueError` | A HURDAT2 line, count, or value cannot be parsed; the message names the line |
| `ValueError` | built-in | A multi-message GRIB2 file opened without `select`, a `select` that matches no message at all, selected messages on different grids, or, under `strict`, a `select` value that matched none of them |

Missing local files and pandas, xarray, or ecCodes parsing failures propagate
unchanged. CSV headers must be unique and non-empty, and an ERDDAP units row
must match the header width.
