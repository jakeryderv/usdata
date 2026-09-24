# RAP model output

Available since v0.20.0 as `noaa:rap`. The Rapid Refresh is NOAA's hourly-cycled
13 km North American model, the parent HRRR nests inside. Its GRIB2 output
lives in the anonymous `noaa-rap-pds` S3 bucket as
`rap.YYYYMMDD/rap.tHHz.<family>fNN.grib2`, one whole file per run, forecast
hour, and grid family, each beside a `.grib2.idx` sidecar. No AWS credentials
or SDK are needed. The adapter shares its run selection with
[HRRR](noaa-hrrr.md); read that page's explanation of runs, cycles, and valid
times first.

## Runs, cycles, and valid times

RAP runs every hour; `cycle` (required) names the run's UTC hour, 0 to 23.
The query window selects runs by **initialization time**, inclusive, and
spans at most one day; a bare date as both bounds is that whole day and
selects its `cycle` run. A window containing no `cycle` initialization is
rejected before any request.

--8<-- "_snippets/utc-window.md"

`forecast_hour` (required) is an integer, a list, or a comma-separated string.
The 03, 09, 15, and 21 UTC runs extend to 51 hours; every other run stops at
21. Hours outside the run's range are rejected before any request; an hour the
archive lacks for an existing run is reported by name after the listing. Asset
times record each file's valid time, initialization plus forecast hour.

## File families and sizes

| `file` | Object name | Content | Size (2024-05-06 20Z, f00) |
|---|---|---|---|
| `awp130` (default) | `awp130pgrbf` | 13 km CONUS Lambert grid, 451 × 337 points, pressure levels plus surface and derived fields: CAPE, CIN, helicity, reflectivity, 2 m and 10 m fields | 18 MB |
| `awp130b` | `awp130bgrbf` | The remaining, less common fields on the same grid | 41 MB |
| `prs` | `wrfprsf` | Pressure-level fields on the model's native rotated grid | 228 MB |
| `nat` | `wrfnatf` | Native hybrid-level fields on the native grid | 305 MB |

The 20 km, 32 km, and 40 km families (`awp252`, `awip32`, `awp236`), the
`wrfmsl` files, and the BUFR soundings are out of scope. Every file is a whole
grid of hundreds of fields; the 13 km analysis holds 355 messages. `variables`,
text, and geographic constraints are rejected because the server cannot
subset the files. Check what a query will download before fetching:

```sh
uv run usdata fetch noaa:rap \
  --start 2024-05-06T20:00Z --end 2024-05-06T20:00Z \
  -p cycle=20 -p forecast_hour=0,1 --dry-run
```

## Fetching selected messages

`messages` fetches only the GRIB2 messages you name, as byte ranges of the
object, exactly as the [HRRR guide](noaa-hrrr.md#fetching-selected-messages)
describes. The sidecar is the key plus `.idx`. Selectors observed in the
2024-05-06 20Z `awp130pgrb` analysis:

| Field | `messages` |
|---|---|
| Surface-based CAPE and CIN | `CAPE:surface`, `CIN:surface` |
| 0–1 km and 0–3 km storm-relative helicity | `HLCY:1000-0 m above ground`, `HLCY:3000-0 m above ground` |
| Mixed-layer CAPE (lowest 90 hPa) | `CAPE:90-0 mb above ground` |
| Most-unstable CAPE (lowest 180 hPa) | `CAPE:180-0 mb above ground` |
| Composite reflectivity | `REFC:entire atmosphere` |
| 2 m temperature and dewpoint | `TMP:2 m above ground`, `DPT:2 m above ground` |

```sh
uv run usdata fetch noaa:rap \
  --start 2024-05-06T20:00Z --end 2024-05-06T20:00Z \
  -p cycle=20 -p forecast_hour=0 \
  -p messages="CAPE:surface,HLCY:3000-0 m above ground" --dry-run
```

Those two fields are about 80 KB of the 18 MB file. RAP packs the wind
components of each level into one GRIB2 message holding two fields, which
the index numbers `12.1` and `12.2` at one offset; naming either fetches the
message whole, and the reader opens both. The fetched file is the messages
concatenated, which is itself a valid GRIB2 file, and its lockfile entry pins
the byte ranges and the object's ETag
([ADR 0028](https://github.com/jakeryderv/usdata/blob/main/docs/adr/0028-partial-grib2-fetch-through-index-files.md)).

## Reading fields

The `grib` extra opens a file with `FetchedAsset.open(select=...)` as an
xarray Dataset; a file fetched with `messages` is already a selection and
opens without `select`. The `awp130` grid is Lambert conformal, so the reader
attaches two-dimensional `latitude` and `longitude` coordinates of shape
(337, 451); longitudes use the 0–360 convention. See the
[HRRR guide](noaa-hrrr.md#reading-fields) for the `select` keys, which are the
same ecCodes names, and the [reader reference](../reference/readers.md) for
the extra's platform support.

## Archive coverage

The bucket's `rap.` day prefixes begin on 2021-02-22, whose 00 UTC run holds
`awp130pgrbf00`; earlier day prefixes hold only NARRE files. Windows before
that run are rejected before any request. The
[NODD registry entry](https://registry.opendata.aws/noaa-rap/) documents public
cloud access, and the
[RAP product page](https://rapidrefresh.noaa.gov/) describes the model.

See the [service research notes](noaa-services.md#rap-model-output) for dated
upstream probes.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Resolution: the 451 × 337 Lambert grid at 13.545 km, read from a fetched
  `awp130pgrb` message with ecCodes on 2026-09-16, and the
  [RAP product page](https://rapidrefresh.noaa.gov/).
- Updates, citation, and terms: the [NODD registry
  entry](https://registry.opendata.aws/noaa-rap/) and the [NOAA Open Data
  Dissemination](https://www.noaa.gov/information-technology/open-data-dissemination)
  statement it quotes.
- Forecast-hour schedule: bounded listings of every cycle of `rap.20240506/`
  on 2026-09-16, 22 files for most cycles and 52 for 03, 09, 15, and 21 UTC.
- Variables: the `messages` table above. A file holds several hundred fields,
  so the entry lists only the ones this guide and the example use.
- Longest query window: `MAX_WINDOW` in `usdata.providers.noaa.hrrr`, which this adapter
  shares through `ModelRuns`.
- Latency is empty: NODD states no lag between a run's initialization and its
  appearance.

[All NOAA datasets](noaa.md).

--8<-- "generated/catalog/noaa/rap.md"
