# GOES GLM lightning detections

Available since v0.15.0 as `noaa:goes-glm`. The Geostationary Lightning Mapper
Level 2 product, `GLM-L2-LCFA`, records lightning events, the groups they form,
and the flashes those groups form, in one NetCDF4 file every 20 seconds. Files
live in the same anonymous `noaa-goes16`, `noaa-goes17`, `noaa-goes18`, and
`noaa-goes19` buckets and `PRODUCT/YYYY/DDD/HH/` layout as
[ABI imagery](noaa-goes.md). No AWS credentials or SDK are needed.

Require `satellite` (16, 17, 18, or 19) and both timestamps. There is no
channel or product parameter. Unknown parameters, text/geographic constraints,
and `variables` are rejected: each file is the whole detection table for its 20
seconds over the satellite's full field of view, and the server cannot crop it.
`temporal_subset` means selecting archived files.

The adapter lists hourly `GLM-L2-LCFA/YYYY/DDD/HH/` prefixes, follows S3
continuation tokens, and selects files whose **start times** fall in the
inclusive UTC query interval. A query spans at most one day. That is
shorter than ABI's seven days because GLM writes 180 files an hour: one day of
one satellite is 4,320 files and about 1.4 GB, and a listing alone is 24 S3
requests. Split longer intervals, and prefer minutes around an event.

--8<-- "_snippets/utc-window.md"

For example, fetch the single file starting at 20:00:00 UTC on 2024-05-06
(about 290 kB):

```sh
uv run usdata fetch noaa:goes-glm \
  --start 2024-05-06T20:00:00Z --end 2024-05-06T20:00:00Z -p satellite=16
```

## Reading detections

The `netcdf` extra opens a file with `FetchedAsset.open()` as an xarray Dataset.
Events, groups, and flashes are separate one-dimensional tables along
`number_of_events`, `number_of_groups`, and `number_of_flashes`, linked by
`event_parent_group_id` and `group_parent_flash_id`. To work with flashes as a
pandas table, select the flash variables and drop the scalar coordinates:

```python
from usdata import pull

(item,) = pull("dataset.yaml").fetched
detections = item.open()
flashes = (
    detections[
        [
            "flash_time_offset_of_first_event",
            "flash_time_offset_of_last_event",
            "flash_lat",
            "flash_lon",
            "flash_area",
            "flash_energy",
            "flash_quality_flag",
        ]
    ]
    .reset_coords(drop=True)
    .to_dataframe()
)
nearby = flashes[flashes.flash_lat.between(33, 38) & flashes.flash_lon.between(-100, -94)]
```

Flash times are decoded CF datetimes. The first event of a flash can precede
the file's nominal start by a fraction of a second, so filter on the decoded
times rather than assuming every row lies inside the 20-second window. Energy
is in joules and area in square metres, with `valid_range` and
`flash_quality_flag` describing the source's own screening. The reader
preserves raw bytes and does not project, deduplicate, or reinterpret
detections; combining files across a window is the caller's concatenation.

## Archive coverage

Listing `GLM-L2-LCFA/2018/` on GOES-16 day by day found the first public file
at 2018-02-13T16:10:00Z (day 044); days 001 through 043 and all of 2017 are
empty. The catalog's start records that first GOES-16 file, not a claim that
every satellite was operating then. Satellite availability varies by date and
outages; no East/West alias is inferred from a historical query.
[NOAA's product documentation](https://www.ncei.noaa.gov/products/goes-terrestrial-weather-abi-glm)
describes the instrument and its field of view; the
[NODD registry](https://registry.opendata.aws/noaa-goes/) documents public cloud
access.

See the [service research notes](noaa-services.md#goes-glm-lightning-detections)
for dated upstream probes.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Resolution: the [NCEI ABI and GLM product
  page](https://www.ncei.noaa.gov/products/goes-terrestrial-weather-abi-glm), which
  gives GLM a spatial resolution of 8 to 14 km; the 20-second file cadence is the
  product's own.
- Updates, citation, and terms: the [NODD registry
  entry](https://registry.opendata.aws/noaa-goes/) and the [NOAA Open Data
  Dissemination](https://www.noaa.gov/information-technology/open-data-dissemination)
  statement it quotes.
- Variables: the flash, group, and event tables described above, with the units the
  files carry.
- Longest query window: `MAX_WINDOW` in `usdata.providers.noaa.glm`.
- Latency is empty: NODD states only that new data is added as soon as it is available.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/goes-glm.md#catalog-reference).
