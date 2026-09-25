# Reader options

How each reader behaves is explained in [readers](../concepts/readers.md).
This page lists what to install, what `open()` infers, and what each format's method accepts.

## Readers and extras

| Format | Method | Extra | Returns | Inferred for |
|---|---|---|---|---|
| CSV | `open_csv` | `pandas` | pandas DataFrame | `text/csv`, `application/csv` (charset parameters allowed); `application/gzip` or `application/x-gzip` when the id ends in `.csv.gz` |
| ERDDAP CSV | `open_csv` | `pandas` | pandas DataFrame with `attrs["units"]` | CSV media types on an asset whose protocol is ERDDAP, and `noaa:ibtracs` CSV assets, whose units row has the same layout; for IBTrACS only a single space or an empty field is missing, so the basin code `NA` stays text |
| HURDAT2 | `open()` only | `pandas` | pandas DataFrame, one row per track point | `noaa:hurdat2` assets, or ids `hurdat2-*.txt` |
| AQS daily JSON | `open()` only | `pandas` | pandas DataFrame, one row per monitor, local day, and pollutant standard; `date_local` and `date_of_last_change` as naive dates, the header in `attrs["usdata"]["header"]` | `epa:aqs-daily` assets, or ids `aqs-daily_*.json` |
| NEXRAD Level II | `open_nexrad` | `radar` | xarray DataTree | `noaa:nexrad-level2` assets |
| NetCDF4 | `open_netcdf` | `netcdf` | xarray Dataset | `application/x-netcdf`, `application/netcdf`, `application/x-netcdf4` |
| GRIB2 | `open_grib2` | `grib` | xarray Dataset | `application/x-grib2`, `application/grib2`, `application/x-grib`, `application/wmo-grib2`; ids ending `.grib2`, `.grb2`, or their `.gz` forms when the media type is missing, generic, or gzip |

`noaa:nexrad-level3` assets have no reader and `open()` raises
`UnsupportedFormat`. Install extras as `pip install "usdata[pandas,grib]"`; the
[Install](../install.md) page has the platform notes for `grib`.

## Options

`open()` takes no options. Each format with options has its own method on
`FetchedAsset`, and a function of the same name in `usdata.readers` that takes
the fetched asset first. A method opens the file as that format whatever its
metadata says, so it is also how a file with ambiguous metadata is opened.
HURDAT2 and AQS files take no options and are opened with `open()`.

| Method | Returns | Option | Behavior |
|---|---|---|---|
| `open_csv` | pandas DataFrame | `dtype` | Mapping of column names to pandas dtype strings; overrides the identifier defaults below. |
| | | `parse_dates` | Columns to parse as dates. Nothing is parsed by default; `dtype={"DATE": "string"}` keeps numeric-looking labels as text. |
| | | `usecols` | Columns to read, in pandas order. |
| | | `nrows` | Maximum observation rows, excluding header and units rows. |
| | | `units_row` | Whether a units row follows the header, as in ERDDAP CSV; `None`, the default, infers it as `open()` does. |
| `open_nexrad` | xarray DataTree | `sweep` | Zero-based integer or non-empty list of distinct integers; `None` opens every sweep. |
| `open_grib2` | xarray Dataset | `select` | Mapping of ecCodes key names to one value or a list of values; required when a file holds more than one message. |
| | | `strict` | `True` raises when a `select` value matches none of the selected messages; the default warns and returns the rest. |
| `open_netcdf` | xarray Dataset | | No options. |

The return types are declared for type checkers, so an editor knows what each
method returns once the extra that provides the type is installed; `open()`
returns `Any` because its result depends on the file.

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
`KeyError` naming the ones it does. Both start from each message's `base_name`
on `GribMessage`: its `shortName`, or for a parameter ecCodes has no name for,
the MRMS product or `parameter_<discipline>_<category>_<number>`.

## CSV identifier defaults

These column names, matched case-insensitively, default to pandas string dtype
so leading zeros survive: `STATION`, `station_id`, `site_no`,
`monitoring_location_id`, `parameter_code`, `statistic_id`, `event_id`,
`episode_id`, `state_fips`, `cz_fips`, `tor_other_cz_fips`. No padding is
added; other numeric-looking ids need an explicit `dtype`. Other columns use
pandas inference and default missing-value parsing.

## Result attributes

| Format | Where | Contents |
|---|---|---|
| CSV, HURDAT2, AQS | `frame.attrs["usdata"]` | Asset id, the asset's request `properties` (a mapping, empty when it records none), and a JSON-compatible copy of its provenance |
| CSV with a units row | `frame.attrs["units"]` | Units row, filtered to the selected columns |
| NEXRAD Level II | `radar.attrs["usdata"]` | Asset id, `properties`, provenance, and `sweeps` listing the returned groups |
| NetCDF4, GRIB2 | `dataset.attrs["usdata"]` | Asset id, `properties`, and provenance |
| GRIB2 | `dataset.attrs["usdata"]["messages"]` | Each variable name mapped to its message's `file_index`, `object_index`, `shortName`, `typeOfLevel`, `level`, and `step`, plus the `selector` a partial fetch asked for |
| `grib2` | per-variable `attrs` | `units` in UDUNITS notation (`J kg-1` where ecCodes writes `J kg**-1`, with the file's spelling in `GRIB_units` whenever the two differ), `name`, `typeOfLevel`, `level`, discipline, category, and parameter numbers, packing type, reference and valid times, step; projection parameters on the Dataset for projected grids |

## Errors

| Error | From `usdata.readers` | Raised when |
|---|---|---|
| `MissingReaderDependency` | subclass of `ImportError` | The extra is not installed; the message names it, and for `grib` also names the ecCodes library when the binding is present but the library is not |
| `UnsupportedFormat` | subclass of `ValueError` | `open()` finds no reader for the asset, or the asset is a Level III product |
| `RadarDecodeError` | subclass of `ValueError` | Moment and coordinate records do not align for the requested sweeps |
| `Hurdat2FormatError` | subclass of `ValueError` | A HURDAT2 line, count, or value cannot be parsed; the message names the line |
| `ValueError` | built-in | A multi-message GRIB2 file opened without `select`, a `select` that matches no message at all, selected messages on different grids, or, under `strict`, a `select` value that matched none of them |

Missing local files and pandas, xarray, or ecCodes parsing failures propagate
unchanged. CSV headers must be unique and non-empty, and an ERDDAP units row
must match the header width.
