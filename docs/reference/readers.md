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

Passing an option to a reader it does not apply to raises `ValueError`, even
with an empty value.

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
| `grib2` | per-variable `attrs` | `units`, `name`, `typeOfLevel`, `level`, discipline, category, and parameter numbers, packing type, reference and valid times, step; projection parameters on the Dataset for projected grids |

## Errors

| Error | From `usdata.readers` | Raised when |
|---|---|---|
| `MissingReaderDependency` | subclass of `ImportError` | The extra is not installed; the message names it, and for `grib` also names the ecCodes library when the binding is present but the library is not |
| `UnsupportedFormat` | subclass of `ValueError` | No reader matches, an unknown `reader` name is passed, or the asset is a Level III product |
| `RadarDecodeError` | subclass of `ValueError` | Moment and coordinate records do not align for the requested sweeps |
| `Hurdat2FormatError` | subclass of `ValueError` | A HURDAT2 line, count, or value cannot be parsed; the message names the line |
| `ValueError` | built-in | A multi-message GRIB2 file opened without `select`, or selected messages on different grids |

Missing local files and pandas, xarray, or ecCodes parsing failures propagate
unchanged. CSV headers must be unique and non-empty, and an ERDDAP units row
must match the header width.
