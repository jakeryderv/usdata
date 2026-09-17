# NBM forecast guidance

Available since v0.20.0 as `noaa:nbm`. The National Blend of Models is NOAA's
statistically blended, bias-corrected forecast guidance, issued hourly and
built from many models rather than run as one. Its GRIB2 `core` output lives in
the anonymous `noaa-nbm-grib2-pds` S3 bucket as
`blend.YYYYMMDD/HH/core/blend.tHHz.core.fFFF.<region>.grib2`, one whole file
per run, forecast hour, and region, each beside a `.grib2.idx` sidecar. No AWS
credentials or SDK are needed. The adapter shares its run selection with
[HRRR](noaa-hrrr.md); read that page's explanation of runs, cycles, and valid
times first.

## Runs, cycles, and valid times

NBM runs every hour; `cycle` (required) names the run's UTC hour, 0 to 23.
The query window selects runs by **initialization time**, inclusive, and
spans at most one day; a bare date as both bounds is that whole day and
selects its `cycle` run. A window containing no `cycle` initialization is
rejected before any request.

--8<-- "_snippets/utc-window.md"

`forecast_hour` (required) is an integer, a list, or a comma-separated string
from 1 to 264; there is no hour 0. Which hours a run publishes depends on the
cycle, so the adapter does not encode the schedule: an hour the run lacks is
reported by name after the listing. Observed for the CONUS files of
2024-05-06:

| Cycles | Hours |
|---|---|
| 00, 12 UTC | Hourly to 36, then every 3 hours to 192 |
| 06, 18 UTC | Hourly to 36, every 3 hours to 192, then every 6 hours to 264 |
| 01, 13 UTC | Hourly to 173 |
| 07, 19 UTC | Hourly to 152 |
| Every other cycle | Hourly to 36 or 37, every 3 hours to about 190, then every 6 hours to about 262, ending on a synoptic valid time |

Asset times record each file's valid time, initialization plus forecast hour.

## Regions and sizes

| `region` | Grid | Size (2024-05-06 20Z, f001) |
|---|---|---|
| `co` (default) | 2.5 km Lambert conformal CONUS, 2345 × 1597 points | 171 MB |
| `ak` | Alaska | 52 MB |
| `hi` | Hawaii | 6 MB |
| `pr` | Puerto Rico | about 3 MB |
| `gu` | Guam | 0.6 MB |

The `qmd` percentile files and the `text` bulletins are out of scope. A CONUS
hour holds 300 messages, so whole-file downloads add up fast: prefer
`messages`. `variables`, text, and geographic constraints are rejected because
the server cannot subset the files.

## Fetching selected messages

`messages` fetches only the GRIB2 messages you name, as byte ranges of the
object, exactly as the [HRRR guide](noaa-hrrr.md#fetching-selected-messages)
describes. NBM index lines carry a further text for ensemble statistics and
probability thresholds, so `TMP:2 m above ground` names the value alone and
`TMP:2 m above ground:1 hour fcst:ens std dev` names its spread. Selectors
observed in the 2024-05-06 20Z CONUS f001 file:

| Field | `messages` |
|---|---|
| 2 m temperature | `TMP:2 m above ground` |
| 2 m dewpoint | `DPT:2 m above ground` |
| 1-hour precipitation | `APCP:surface:0-1 hour acc fcst` |

```sh
uv run usdata fetch noaa:nbm \
  --start 2024-05-06T20:00Z --end 2024-05-06T20:00Z \
  -p cycle=20 -p forecast_hour=1,2,3 -p messages="TMP:2 m above ground" --dry-run
```

Each 2 m temperature message is about 1.5 MB of the 171 MB file. The fetched
file is the messages concatenated, which is itself a valid GRIB2 file, and its
lockfile entry pins the byte ranges and the object's ETag
([ADR 0028](https://github.com/jakeryderv/usdata/blob/main/docs/adr/0028-partial-grib2-fetch-through-index-files.md)).

## Reading fields

The `grib` extra opens a file with `FetchedAsset.open(select=...)` as an
xarray Dataset; a file fetched with `messages` is already a selection and
opens without `select`. The CONUS grid is Lambert conformal, so the reader
attaches two-dimensional `latitude` and `longitude` coordinates of shape
(1597, 2345); longitudes use the 0–360 convention. The 2 m temperature opens
as `2t` in kelvin. See the [reader reference](../reference/readers.md) for the
extra's platform support.

## Archive coverage

The bucket's day prefixes begin on 2020-05-18, but the `core/` layout this
adapter reads begins with the 12 UTC run of 2020-09-29; earlier runs hold a
`grib2/` layout of `master` files that is not reachable here. Windows before
that run are rejected before any request. The
[NODD registry entry](https://registry.opendata.aws/noaa-nbm/) documents
public cloud access, and the
[NBM product page](https://vlab.noaa.gov/web/mdl/nbm) describes the blend.

See the [service research notes](noaa-services.md#nbm-forecast-guidance) for
dated upstream probes.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Resolution: the 2345 × 1597 Lambert grid at 2.54 km, read from a fetched
  CONUS message with ecCodes on 2026-09-16, and the
  [NBM product page](https://vlab.noaa.gov/web/mdl/nbm).
- Updates, citation, and terms: the [NODD registry
  entry](https://registry.opendata.aws/noaa-nbm/) and the [NOAA Open Data
  Dissemination](https://www.noaa.gov/information-technology/open-data-dissemination)
  statement it quotes.
- Forecast-hour schedule: bounded listings of every cycle of `blend.20240506/`
  on 2026-09-16, tabulated above.
- Variables: the `messages` table above. A file holds hundreds of fields, so
  the entry lists only the ones this guide and the example use.
- Longest query window: `MAX_WINDOW` in `usdata.providers.noaa.hrrr`, which this adapter
  shares through `ModelRuns`.
- Latency is empty: NODD states no lag between a run's initialization and its
  appearance.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/nbm.md#catalog-reference).
