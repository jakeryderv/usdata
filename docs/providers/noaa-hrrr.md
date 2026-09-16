# HRRR model output

Available since v0.15.0 as `noaa:hrrr`. The High-Resolution Rapid Refresh is
NOAA's 3 km, hourly-cycled CONUS forecast model. Its GRIB2 output lives in the
anonymous `noaa-hrrr-bdp-pds` S3 bucket as `hrrr.YYYYMMDD/conus/hrrr.tHHz.<variant>fNN.grib2`,
one whole file per run and forecast hour. No AWS credentials or SDK are needed.

## Runs, cycles, and valid times

A **run** (or cycle) is one model initialization, named by its UTC day and
hour: `hrrr.20240506/.../hrrr.t20z.` is the run started at 20 UTC on
2024-05-06. Each run writes forecast hours `f00`, `f01`, … The **valid time**
of a file is the initialization plus its forecast hour: `t20z.wrfsfcf03` is
valid at 23 UTC. `f00` is the analysis, the model's best estimate of the
atmosphere at initialization; for environmental parameters around an observed
event, `f00` or `f01` of the nearest run is usually what you want.

The query window selects runs by **initialization time**, inclusive, and spans
at most one day. `cycle` (required) names the hour; a run is selected when its
initialization falls inside the window, so a window from 20:00 to 20:00 UTC on
one day with `cycle=20` selects exactly that run, and a 24-hour window can
select the same cycle on two days. A window that contains no `cycle`
initialization is rejected before any request.

--8<-- "_snippets/utc-window.md"

`forecast_hour` (required) is an integer, a list, or a comma-separated string.
The 00, 06, 12, and 18 UTC runs extend to 48 hours; every other run stops at
18. Hours outside the run's range are rejected before any request; an hour the
archive lacks for an existing run is reported by name after the listing. Asset
times record each file's valid time.

## File variants and sizes

| `file` | Object name | Content | Size (2024-05-06 20Z, f00) |
|---|---|---|---|
| `sfc` (default) | `wrfsfcf` | 2-D surface and derived fields: CAPE, CIN, helicity, reflectivity, 2 m and 10 m fields, precipitation | 150 MB |
| `prs` | `wrfprsf` | Fields on isobaric levels | 409 MB |
| `nat` | `wrfnatf` | Fields on native hybrid levels | 706 MB |

Later forecast hours are slightly larger. Subhourly output (`wrfsubhf`,
15-minute steps), the `alaska` domain, BUFR soundings, and the `.grib2.idx`
sidecars are out of scope. Every file is a whole CONUS grid of many fields;
`variables`, text, and geographic constraints are rejected because the server
cannot subset them. Check what a query will download before fetching:

```sh
uv run usdata fetch noaa:hrrr \
  --start 2024-05-06T20:00Z --end 2024-05-06T20:00Z \
  -p cycle=20 -p forecast_hour=0,1 --dry-run
```

Remove `--dry-run` to download about 310 MB. Cached bytes are the exact
objects; lockfiles pin their checksums like every other dataset.

## Reading fields

The `grib` extra opens a file with `FetchedAsset.open(select=...)` as an
xarray Dataset. A surface file holds 170 messages, so `select` is required to
choose them by ecCodes keys; opening without it lists the available
`(shortName, typeOfLevel, level)` triples. Keys observed in the 2024-05-06 20Z
surface analysis:

| Field | `select` |
|---|---|
| Surface-based CAPE, J/kg | `{"shortName": "cape", "typeOfLevel": "surface"}` |
| Surface-based CIN, J/kg | `{"shortName": "cin", "typeOfLevel": "surface"}` |
| 0–3 km storm-relative helicity, m²/s² | `{"shortName": "hlcy", "typeOfLevel": "heightAboveGroundLayer", "level": 3000}` |
| 0–1 km storm-relative helicity | `{"shortName": "hlcy", "typeOfLevel": "heightAboveGroundLayer", "level": 1000}` |
| Composite reflectivity, dBZ | `{"shortName": "refc"}` |
| 10 m wind components, m/s | `{"shortName": ["10u", "10v"]}` |
| 2 m temperature and dewpoint, K | `{"shortName": ["2t", "2d"]}` |
| Mixed-layer CAPE (lowest 90 hPa) | `{"shortName": "cape", "typeOfLevel": "pressureFromGroundLayer", "level": 9000}` |

```python
from usdata import pull

(item,) = pull("dataset.yaml").fetched
environment = item.open(select={"shortName": ["cape", "cin"], "typeOfLevel": "surface"})
```

The grid is Lambert conformal, 1799 × 1059 points at 3 km; the reader attaches
two-dimensional `latitude` and `longitude` coordinates and the projection
parameters as attributes. Several HRRR fields use local parameter tables that
ecCodes reports as `unknown`; select those by `typeOfLevel` and `level`, or by
discipline, category, and parameter number. See the
[reader reference](../reference/readers.md) for the extra's platform support
and limits. The adapter preserves raw bytes and computes no derived
parameters.

## Archive coverage

The bucket's day prefixes begin on 2014-07-30, whose first CONUS run is 18 UTC.
Model versions changed over the archive (HRRRv3 in 2018 extended the 00/06/12/18
UTC runs to 48 hours; HRRRv4 in December 2020 changed field lists), so older
runs may lack hours or fields that recent ones carry; the adapter reports a
missing file by run and hour rather than guessing. The
[NODD registry entry](https://registry.opendata.aws/noaa-hrrr-pds/) documents
public cloud access, and the
[HRRR product page](https://rapidrefresh.noaa.gov/hrrr/) describes the model and
its GRIB2 field inventories.

See the [service research notes](noaa-services.md#hrrr-model-output) for dated
upstream probes.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Resolution: the [HRRR product page](https://rapidrefresh.noaa.gov/hrrr/) for the 3 km
  CONUS grid, with the grid size and forecast-hour schedule confirmed above.
- Updates, citation, and terms: the [NODD registry
  entry](https://registry.opendata.aws/noaa-hrrr-pds/), whose update frequency is
  hourly, and the [NOAA Open Data
  Dissemination](https://www.noaa.gov/information-technology/open-data-dissemination)
  statement it quotes.
- Variables: the `select` table above. A file holds hundreds of fields, so the entry
  lists only the ones this guide and the example use.
- Longest query window: `MAX_WINDOW` in `usdata.providers.noaa.hrrr`.
- Latency is empty: NODD states no lag between a run's initialization and its
  appearance.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/hrrr.md#catalog-reference).
