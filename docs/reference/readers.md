# Opening fetched data

Available from source for v0.6. CSV readers require the optional pandas extra.
Follow [development setup](../../README.md#development), then install it with
`uv sync --all-groups --extra pandas`. Once released, install `usdata[pandas]`
with pip or add it to a project with `uv add "usdata[pandas]"`.

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

`FetchedAsset.open()` returns an in-memory pandas DataFrame. It recognizes
`text/csv` and `application/csv` (including charset parameters). An ERDDAP asset
uses the `erddap-csv` reader, which consumes the second CSV record as units.
Other CSV assets use the ordinary `csv` reader. This assumes ERDDAP's standard
`.csv` response, not its headerless or units-free variants.

| Option | Behavior |
|---|---|
| `reader` | Defaults to inference. Explicit `"csv"` or `"erddap-csv"` handles missing or ambiguous media metadata. |
| `dtype` | Mapping of column names to pandas dtype strings; overrides identifier defaults for those columns. |
| `parse_dates` | List of columns to parse as dates/timestamps. Dates stay strings by default. |
| `usecols` | List of columns to read. Ordering follows pandas behavior. |
| `nrows` | Maximum number of observation rows to read, excluding headers and units. |

`STATION` and other case-insensitive identifier names (`station_id`, `site_no`,
`monitoring_location_id`, `parameter_code`, `statistic_id`) default to pandas
string dtype so leading zeros survive. Other columns use pandas type inference
and default missing-value parsing. Numeric-looking IDs with other column names
need an explicit string dtype. Pass an explicit dtype to change a default.

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

## Boundaries and errors

Opening is local and does not re-fetch, verify checksums, alter cached files,
update provenance, or write transformed data. Run `verify` when checking locked
input integrity; call `pull` to restore missing files. Editing the DataFrame
does not change its source CSV. Scientific units are not converted, and
provider-specific missing-data sentinels are not normalized beyond pandas defaults.

`MissingReaderDependency` (an `ImportError`) names `usdata[pandas]` when pandas
is absent. Unsupported formats or reader names raise `UnsupportedFormat`
(a `ValueError`). Both errors are available from `usdata.readers`. Missing local
files and pandas parsing/conversion failures propagate normally. CSV headers
must have unique, non-empty names, and ERDDAP units must match the header width.

NetCDF, NEXRAD binary, GRIB, and geospatial readers are not implemented. Use the
fetched path with a suitable external reader for those formats. The core SDK,
CLI, fetch, cache, and lockfile workflows continue to work without pandas.
