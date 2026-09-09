# Opening fetched data

Available since v0.6. Install the optional pandas extra with
`pip install "usdata[pandas]"` or `uv add "usdata[pandas]"`.
For a source checkout, follow [development setup](../../README.md#development)
and run `uv sync --group dev --extra pandas`.

```python
from usdata import build_query, get
from usdata.fetch import fetch

items = fetch(
    get("noaa:coastwatch-sst"),
    build_query(
        bbox=(-80.08, 30.02, -80.02, 30.08),
        start="2024-05-06T12:00Z",
        end="2024-05-06T12:00Z",
    ),
)
frame = items[0].open(parse_dates=["time"])
print(frame["analysed_sst"].mean(), frame.attrs["units"]["analysed_sst"])
```

The same method works on `pull(...).fetched` results, including locked cache
restoration. See the runnable [SST example](../../examples/sst-analysis/README.md).

## Selection and options

For CSV, `FetchedAsset.open()` returns an in-memory pandas DataFrame. It recognizes
`text/csv` and `application/csv` (including charset parameters). An ERDDAP asset
uses the `erddap-csv` reader, which consumes the second CSV record as units.
Other CSV assets use the ordinary `csv` reader. This assumes ERDDAP's standard
`.csv` response, not its headerless or units-free variants.

Gzip CSV opening is available from source for v0.8. Gzip media types
(`application/gzip`, `application/x-gzip`) are recognized only when the asset ID
ends with `.csv.gz`; ambiguous compressed files need an explicit `reader="csv"`.
The reader checks gzip magic in the local file and decompresses through a stream,
without rewriting the archive, downloading anything, or changing its provenance.
Corrupt gzip/CSV errors propagate. `nrows` limits parsed rows and does not verify
the entire compressed archive; use the ordinary cache/lockfile verification for
source integrity.

| Option | Behavior |
|---|---|
| `reader` | Defaults to inference. Explicit `"csv"`, `"erddap-csv"`, or `"nexrad-level2"` handles missing or ambiguous media metadata. |
| `dtype` | Mapping of column names to pandas dtype strings; overrides identifier defaults for those columns. |
| `parse_dates` | List of columns to parse as dates/timestamps. Dates stay strings by default. |
| `usecols` | List of columns to read. Ordering follows pandas behavior. |
| `nrows` | Maximum number of observation rows to read, excluding headers and units. |

`STATION` and other case-insensitive identifier names (`station_id`, `site_no`,
`monitoring_location_id`, `parameter_code`, `statistic_id`) default to pandas
string dtype so leading zeros survive. Other columns use pandas type inference
and default missing-value parsing. Numeric-looking IDs with other column names
need an explicit string dtype. Pass an explicit dtype to change a default. From source
for v0.8, `event_id`, `episode_id`, `state_fips`, `cz_fips`, and
`tor_other_cz_fips` also retain source strings. No padding is added: Storm Events
zone codes are not automatically converted to Census county identifiers.

```python
frame = items[0].open(usecols=["time", "analysed_sst"], nrows=100)
```

ERDDAP units are retained in `frame.attrs["units"]`, filtered to selected
columns. USGS per-observation units and quality columns remain ordinary columns.
`frame.attrs["usdata"]` contains the asset ID and a JSON-compatible copy of its
original provenance. This metadata describes the source bytes, not any analysis
you perform afterward. DataFrame operations/exports may discard attributes;
keep lockfiles and provenance sidecars as the persistent record.

Pandas documents [CSV conversion options](https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html)
and [DataFrame attributes](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.attrs.html).
For parser options outside this small API, use pandas directly on `item.path`,
accounting for ERDDAP's units record yourself.

## NEXRAD Level II

Available from source for v0.8; the published v0.7 package does not include the
radar extra. Use the checkout commands below until v0.8 is published.

Install `usdata[radar]` (checkout: `uv sync --group dev --extra radar`). Assets
from `noaa:nexrad-level2` infer the radar reader; use `reader="nexrad-level2"`
for an archive with ambiguous dataset metadata. Whole-file gzip/bzip2 and
internal Archive II compression are supported, with offline legacy message-1
and modern message-31 fixtures. The radar extra is verified on Linux Python
3.11 and 3.14; core and CSV readers retain their existing platform coverage.

```python
radar = item.open()  # a fetched noaa:nexrad-level2 asset
sweep = radar["sweep_0"].to_dataset()
print(sweep["DBZH"].attrs["units"])  # dBZ
print(radar.attrs["usdata"]["provenance"]["checksum"])
```

The result is an eagerly loaded **xarray DataTree**, decoded by
[xradar](https://docs.openradarscience.org/projects/xradar/en/stable/generated/xradar.io.backends.nexrad_level2.open_nexradlevel2_datatree.html).
Each `sweep_N` child has native fields and coordinates. Decoder resources are
closed before returning. A compressed volume can expand to hundreds of MB;
select a bounded time/site query before fetching. CSV options raise `ValueError`
for radar rather than being ignored.

Units and native moment scaling are retained. Reserved codes become NaN:
0–1 for DBZH (reflectivity), VRADH (radial velocity), WRADH (spectrum width), ZDR,
PHIDP, and RHOHV; 0–7 for CCORH (clutter-filter power removed). Coordinates and
unknown fields are unchanged. These are parsing conventions, not quality
control; no rainfall conversion, clutter removal, or velocity unfolding is
performed. Incomplete sweeps are padded with NaN so received rays remain
available. Xradar warnings about angle reconstruction are preserved; do not
interpret those sweeps as complete observations. Legacy files may lack location
metadata, which the reader does not replace with guessed coordinates.

Root `radar.attrs["usdata"]` carries the asset ID and copied source provenance;
it is not an export format or a record of analysis steps. Keep the input files
and sidecars. See the [executed radar notebook](../../examples/radar-reflectivity/example.ipynb)
and [ADR 0008](../adr/0008-local-radar-readers.md). Advanced decoder options
remain available by calling xradar directly with `item.path`.

## Boundaries and errors

Opening is local and does not re-fetch, verify checksums, alter cached files,
update provenance, or write transformed data. Run `verify` when checking locked
input integrity; call `pull` to restore missing files. Editing the DataFrame
does not change its source CSV. Scientific units are not converted, and
CSV provider-specific missing-data sentinels are not normalized beyond pandas defaults.

`MissingReaderDependency` (an `ImportError`) names `usdata[pandas]` or
`usdata[radar]` when the required reader dependency is absent. Unsupported formats or reader names raise `UnsupportedFormat`
(a `ValueError`). Both errors are available from `usdata.readers`. Missing local
files and pandas parsing/conversion failures propagate normally. CSV headers
must have unique, non-empty names, and ERDDAP units must match the header width.

GRIB and geospatial readers are not implemented. Use the
fetched path with a suitable external reader for those formats. The core SDK,
CLI, fetch, cache, and lockfile workflows continue to work without pandas.

## NetCDF4 scenes

Available from source for v0.8. Install `usdata[netcdf]` for xarray plus the
h5netcdf/h5py backend. `item.open()` recognizes `application/x-netcdf`,
`application/netcdf`, and `application/x-netcdf4`; use `reader="netcdf"` when
an archived asset has ambiguous media metadata. No current registry is needed.

The result is an xarray Dataset of the file's root group. CF packed values,
unsigned storage, fill values and time coordinates are decoded; dimensions,
coordinate units, variable units, projection metadata and data-quality flags
are retained. Quality filtering and projection are the caller's responsibility.
`dataset.attrs["usdata"]` contains the same copied source provenance convention
as CSV readers. CSV options (`dtype`, `parse_dates`, `usecols`, `nrows`) are
rejected, including empty values, for NetCDF opening.

The source is opened as a local binary file with a fixed engine. All variables
are loaded into memory and both dataset/backend and file are closed before
returning; callers need not manage a file handle. Memory must fit the decoded
scene, which can be much larger than its compressed download size. The initial
scope is NetCDF4/HDF5; classic NetCDF3, arbitrary HDF5, groups and lazy/dask
opening are not supported. Use a format-specific library on `item.path` for
those cases. Backend parsing errors propagate; missing optional modules name
the `usdata[netcdf]` extra.

See the executed [GOES example](../../examples/goes-imagery/example.ipynb),
[xarray's decoding options](https://docs.xarray.dev/en/stable/generated/xarray.open_dataset.html),
and [ADR 0009](../adr/0009-eager-local-netcdf4-reader.md).
