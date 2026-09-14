# GFS model output

Available since v0.15.0 as `noaa:gfs`. The Global Forecast System is NOAA's
global forecast model, run four times a day. Its GRIB2 output lives in the
anonymous `noaa-gfs-bdp-pds` S3 bucket as
`gfs.YYYYMMDD/HH/atmos/gfs.tHHz.pgrb2.<resolution>.fNNN`, one whole file per
run, forecast hour, and grid resolution. No AWS credentials or SDK are needed.
The adapter shares its run selection with [HRRR](noaa-hrrr.md); read that
page's explanation of runs, cycles, and valid times first.

## Runs, cycles, and valid times

GFS runs at 00, 06, 12, and 18 UTC; `cycle` (required) must be one of those
four hours. The query window selects runs by **initialization time**,
inclusive, and spans at most one day: a window from 00:00 to 00:00 UTC on one
day with `cycle=0` selects exactly that run, and a 24-hour window can select
the same cycle on two days. A window containing no `cycle` initialization is
rejected before any request.

--8<-- "_snippets/utc-window.md"

`forecast_hour` (required) is an integer, a list, or a comma-separated string
from 0 to 384. Which hours exist depends on the grid: the 0.25 degree files are
hourly to 120 and every three hours from 123 to 384; the 0.5 and 1 degree files
are every three hours from 0 to 384. An hour the resolution never publishes is
rejected before any request with the schedule in the message; an hour the
archive lacks for an existing run is reported by name after the listing. Asset
times record each file's valid time, initialization plus forecast hour.

## Resolutions and sizes

| `resolution` | Grid | Files per run | Size (2024-05-06 00Z, f000) |
|---|---|---|---|
| `0p25` (default) | 0.25 degree, 1440 × 721 | 209 | 508 MB |
| `0p50` | 0.5 degree, 720 × 361 | 129 | 150 MB |
| `1p00` | 1 degree, 360 × 181 | 129 | 42 MB |

Later forecast hours are slightly larger. Every `pgrb2` file is a whole global
grid of several hundred fields; the 1 degree analysis holds 696 messages. The
`pgrb2b` files (the remaining, less common fields), `pgrb2full.0p50`, the
`.anl` analysis files, BUFR soundings, the `wave/` component, and the `.idx`
sidecars are out of scope, as are the GEFS ensemble and the pre-v16 layout.
`variables`, text, and geographic constraints are rejected because the server
cannot subset the files. Check what a query will download before fetching:

```sh
uv run usdata fetch noaa:gfs \
  --start 2024-05-06T00:00Z --end 2024-05-06T00:00Z \
  -p cycle=0 -p forecast_hour=0,3 -p resolution=1p00 --dry-run
```

Remove `--dry-run` to download about 87 MB. For environmental parameters
around an observed event, the 1 degree analysis is the cheapest choice; the
0.25 degree files are twelve times larger for the same fields on a finer grid.
Cached bytes are the exact objects; lockfiles pin their checksums like every
other dataset.

## Reading fields

The `grib` extra opens a file with `FetchedAsset.open(select=...)` as an
xarray Dataset. `select` is required to choose messages by ecCodes keys;
opening without it lists the available `(shortName, typeOfLevel, level)`
triples. Keys observed in the 2024-05-06 00Z 1 degree analysis:

| Field | `select` |
|---|---|
| Surface-based CAPE, J/kg | `{"shortName": "cape", "typeOfLevel": "surface"}` |
| Surface-based CIN, J/kg | `{"shortName": "cin", "typeOfLevel": "surface"}` |
| 0–3 km storm-relative helicity, m²/s² | `{"shortName": "hlcy", "typeOfLevel": "heightAboveGroundLayer", "level": 3000}` |
| Composite reflectivity, dB | `{"shortName": "refc"}` |
| 10 m wind components, m/s | `{"shortName": ["10u", "10v"]}` |
| 2 m temperature and dewpoint, K | `{"shortName": ["2t", "2d"]}` |
| Mean sea-level pressure, Pa | `{"shortName": "prmsl"}` |
| Precipitable water, kg/m² | `{"shortName": "pwat"}` |
| Mixed-layer CAPE (lowest 90 hPa) | `{"shortName": "cape", "typeOfLevel": "pressureFromGroundLayer", "level": 9000}` |
| Most-unstable CAPE (lowest 180 hPa) | `{"shortName": "cape", "typeOfLevel": "pressureFromGroundLayer", "level": 18000}` |

```python
from usdata import pull

(item,) = pull("dataset.yaml").fetched
environment = item.open(select={"shortName": ["cape", "cin"], "typeOfLevel": "surface"})
```

The grids are regular latitude-longitude; the reader attaches one-dimensional
`latitude` (90 to -90) and `longitude` (0 to 359.75) coordinates. Longitudes
use the 0–360 convention, so western-hemisphere points need `longitude % 360`
when matching. GFS has no 0–1 km helicity field; only the 0–3 km layer is
published. See the [reader reference](../reference/readers.md) for the extra's
platform support and limits. The adapter preserves raw bytes and computes no
derived parameters.

## Archive coverage

The bucket's day prefixes begin on 2021-01-01, but the `atmos/` layout this
adapter reads begins with the 12 UTC run of 2021-03-22, when GFS v16 was
implemented; earlier cycles hold only WAFS aviation files in the public bucket.
Windows before that run are rejected before any request. The
[NODD registry entry](https://registry.opendata.aws/noaa-gfs-bdp-pds/) documents
public cloud access, and the
[GFS product page](https://www.emc.ncep.noaa.gov/emc/pages/numerical_forecast_systems/gfs.php)
describes the model and its GRIB2 field inventories.

See the [service research notes](noaa-services.md#gfs-model-output) for dated
upstream probes.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/gfs.md#catalog-reference).
