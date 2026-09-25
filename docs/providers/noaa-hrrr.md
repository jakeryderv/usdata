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
select the same cycle on two days. A bare date as both bounds is that whole
day and selects its `cycle` run. A window that contains no `cycle`
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
15-minute steps), the `alaska` domain, and BUFR soundings are out of scope.
Every file is a whole CONUS grid of many fields; `variables`, text, and
geographic constraints are rejected because the server cannot subset them. The
`.grib2.idx` sidecar beside each object is not a separate dataset, but
[`messages`](#fetching-selected-messages) reads it to fetch part of one file.
Check what a query will download before fetching:

```sh
uv run usdata fetch noaa:hrrr \
  --start 2024-05-06T20:00Z --end 2024-05-06T20:00Z \
  -p cycle=20 -p forecast_hour=0,1 --dry-run
```

The listing gives each file's exact size and the total, so remove `--dry-run`
to download about 310 MB. Cached bytes are the exact objects; lockfiles pin
their checksums like every other dataset.

## Fetching selected messages

`messages` fetches only the GRIB2 messages you name, as byte ranges of the
object, instead of the whole file. Name them the way the object's `.idx`
sidecar names them, `SHORTNAME:level text`, with an optional `:step text`:

```sh
uv run usdata fetch noaa:hrrr \
  --start 2024-05-06T20:00Z --end 2024-05-06T20:00Z \
  -p cycle=20 -p forecast_hour=0 \
  -p messages="CAPE:surface,HLCY:3000-0 m above ground" --dry-run
```

```text
hrrr.20240506.t20z.wrfsfcf00.part-13819cd0ccdf.grib2	1838460	s3://noaa-hrrr-bdp-pds/hrrr.20240506/conus/hrrr.t20z.wrfsfcf00.grib2#messages=105,131
1 asset(s) matched, 1838460 bytes
```

That is 1.8 MB instead of 150 MB for the two fields the
[HRRR environment example](https://usdata.dev/datasets/noaa/hrrr/) uses.
The spelling is exact and case-sensitive: short names are upper case (`CAPE`,
`HLCY`, `TMP`), and the level text is the sidecar's own wording, which is
**not** the ecCodes vocabulary `open_grib2(select=...)` takes. `2 m above ground`,
not `heightAboveGround`; `3000-0 m above ground`, not `heightAboveGroundLayer`.
Pass one value, a list, or a comma-separated string; a selector matching no
message is an error listing the levels that short name publishes or the nearest
short names. If the run publishes no index, the query fails rather than
quietly downloading 150 MB.

Common surface-file selectors, read from the 2024-05-06 20Z index:

| Field | `messages` |
|---|---|
| Surface-based CAPE | `CAPE:surface` |
| Surface-based CIN | `CIN:surface` |
| 0–3 km storm-relative helicity | `HLCY:3000-0 m above ground` |
| 0–1 km storm-relative helicity | `HLCY:1000-0 m above ground` |
| Composite reflectivity | `REFC:entire atmosphere` |
| 10 m wind components | `UGRD:10 m above ground`, `VGRD:10 m above ground` |
| 2 m temperature and dewpoint | `TMP:2 m above ground`, `DPT:2 m above ground` |
| Mixed-layer CAPE (lowest 90 hPa) | `CAPE:90-0 mb above ground` |

A selector asks in the index's vocabulary and the reader answers in ecCodes',
and the fetch records which is which, so you never have to guess the pairing.
Provenance stores one selector beside each fetched byte range, `usdata inspect`
prints a `selector` column for a partial file, `attrs["usdata"]["messages"]`
gives each variable a `selector`, and `summary.grib2.variable_for("CAPE:surface")`
returns the variable name that selector produces, `cape_surface_0` for
the two-field fetch above and a bare `cape` had every fetched message shared one
level. A selector no message here was fetched for raises `KeyError` listing the
ones that were.

The fetched file is the selected messages concatenated, which is itself a valid
GRIB2 file: `usdata inspect` lists them and `open()` reads them, with `select`
optional because the fetch already selected. The asset id carries a digest of
the resolved message numbers, so a partial file never collides with the whole
one in the cache, and the lockfile pins the byte ranges and the object's ETag.
A restore re-issues exactly those ranges and never re-reads the index; if the
object has been republished, the ETag no longer matches and the run reports
drift instead of silently mixing revisions. See
[ADR 0028](https://github.com/jakeryderv/usdata/blob/main/docs/adr/0028-partial-grib2-fetch-through-index-files.md).

## Reading fields

The `grib` extra opens a file with `FetchedAsset.open_grib2(select=...)` as an
xarray Dataset. A surface file holds 170 messages, so `select` is required to
choose them by ecCodes keys; opening without it lists the available
`(shortName, typeOfLevel, level)` triples. A file fetched with `messages` is
already a selection, so it opens without `select`. Keys observed in the 2024-05-06 20Z
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
environment = item.open_grib2(select={"shortName": ["cape", "cin"], "typeOfLevel": "surface"})
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
- Message selectors: the run's own `.grib2.idx` sidecar, read on 2026-09-15.
- Latency is empty: NODD states no lag between a run's initialization and its
  appearance.

[All NOAA datasets](noaa.md).

--8<-- "generated/catalog/noaa/hrrr.md"
