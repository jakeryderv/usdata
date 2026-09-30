# GOES ABI imagery and cloud-top products

Available since v0.8 as `noaa:goes-abi`. Files are NetCDF4/HDF5 scenes from the
anonymous `noaa-goes16`, `noaa-goes17`, `noaa-goes18`, and `noaa-goes19` buckets.
No AWS credentials or SDK are needed. The dataset started with single-channel
CONUS Cloud and Moisture Imagery, `ABI-L2-CMIPC`, and added mesoscale imagery in
v0.25.0. It now also covers full-disk imagery, the 16-band imagery files, and
four cloud-top products. L1b radiances and the other Level 2 products are not
supported.

## Products

`product` names one bucket directory exactly. The last letter is the sector:
`C` for CONUS, `F` for full disk, `M` for mesoscale. NOAA does not make every
product for every sector, and the adapter accepts only the directories that
exist:

| Product | What one file holds | CONUS | Full disk | Mesoscale | First archived day |
|---|---|---|---|---|---|
| `ABI-L2-CMIP` | One channel of Cloud and Moisture Imagery, `CMI` and `DQF` | `CMIPC` | `CMIPF` | `CMIPM` | 2017-02-28 |
| `ABI-L2-MCMIP` | All 16 channels on one 2 km grid, `CMI_C01`–`CMI_C16` and `DQF_C01`–`DQF_C16` | `MCMIPC` | `MCMIPF` | `MCMIPM` | 2017-02-28 |
| `ABI-L2-ACHA` | Cloud-top height `HT` (m) | `ACHAC` | `ACHAF` | `ACHAM` | 2019-12-02 |
| `ABI-L2-ACHT` | Cloud-top temperature `TEMP` (K) | none | `ACHTF` | `ACHTM` | 2019-12-05 |
| `ABI-L2-CTP` | Cloud-top pressure `PRES` (hPa) | `CTPC` | `CTPF` | none | 2019-12-05 |
| `ABI-L2-ACTP` | Cloud-top phase `Phase` (categories) | `ACTPC` | `ACTPF` | `ACTPM` | 2017-05-16; `ACTPM` 2019-12-02 |

Write the whole directory name, for example `product=ABI-L2-MCMIPC`. The first
archived day is the earliest scene in any of the four buckets, always GOES-16's;
later satellites start later (GOES-17 in late August 2018, GOES-18 on
2022-05-11, GOES-19 in October 2024). A query that ends before its product's
first day is refused, and one that starts earlier is listed from that day.

Every cloud-top file also holds a `DQF` quality flag. `Phase` values 0 to 5 mean
clear sky, liquid water, supercooled liquid water, mixed phase, ice, and
unknown, as the file's `flag_meanings` states. The files' `spatial_resolution`
attributes give 10 km at nadir for CONUS and full-disk height and pressure, 4 km
for mesoscale height, and 2 km for temperature and phase in every sector.

### The 2 km cloud-top height variant

The buckets also hold `ABI-L2-ACHA2KMC`, `ACHA2KMF`, and `ACHA2KMM`, a 2 km
cloud-top height. Their filenames have the same shape, but they are not
supported: GOES-17 has none, and the other satellites start only in 2023
(GOES-16 on 2023-03-23, GOES-18 on 2023-03-27). Accepting them would mean a
product whose existence depends on the satellite and year, and the 10 km `ACHA`
already covers the whole record. Add them if a study needs the finer grid.

## Selecting

Require `satellite` (16, 17, 18, or 19) and both timestamps. `product`
defaults to `ABI-L2-CMIPC`, so a query written before the new products still
means the same files.

- `channel` (1–16, also `C01`–`C16`) is required for the three `ABI-L2-CMIP`
  products and refused for every other product. An MCMIP file holds all 16
  channels, so a channel there is a mistake rather than a filter.
- `sector` (`M1` or `M2`) is required for the products ending in `M` and refused
  for the rest.

These rules are checked before any network access, and each mistake names the
parameter and the product. Unknown parameters, text or geographic constraints,
and `variables` are refused too: the server cannot crop these scenes or select
variables within them. `temporal_subset` means selecting archived scans.
[ADR 0050](../adr/0050-goes-abi-product-selection.md) records why the parameters
work this way.

The adapter lists hourly `PRODUCT/YYYY/DDD/HH/` prefixes, follows S3
continuation tokens, and selects scans whose **start times** fall in the inclusive
UTC query interval. It does not select a scan that started before the interval
merely because the scan overlaps it. Filename start/end stamps have tenths-of-a-
second precision; asset metadata retains both bounds and the listed byte size.

Both mesoscale sectors share one directory per product; filenames distinguish
`M1` from `M2`, for example `OR_ABI-L2-ACHAM1-M6_G16_s...`. The adapter filters
the requested sector, channel, and satellite, never mixing M1 and M2. A sector
is a movable observation window, not a geographic alias. Inspect the coordinates
and `geospatial_lat_lon_extent` in every file before comparing pixels across
time; scan-start seconds and sector coverage can change. No sector-by-location
selection is inferred.

--8<-- "_snippets/utc-window.md"

## How much a query fetches

A query spans at most seven days, for every product; split longer intervals.
The window bounds how many hourly listings one query makes (at most 169), not
how many bytes its files hold, and those differ greatly. Measured on GOES-16 in
the daytime hour from 22:00 UTC on 2024-05-06, with the last column repeating
that hour for a week:

| Product | Files per hour | MB per file | A week at this rate |
|---|---|---|---|
| `CMIPC`, one channel | 12 | 2.2–63 | 5–122 GB |
| `CMIPF`, one channel | 6 | 9–301 | 10–288 GB |
| `CMIPM`, one channel and sector | 60 | 0.2–5.0 | 2–49 GB |
| `MCMIPC` | 12 | 55–58 | 114 GB |
| `MCMIPF` | 6 | 297–312 | 307 GB |
| `MCMIPM`, one sector | 60 | 4.3–4.5 | 45 GB |
| `ACHAC`, `CTPC`, `ACTPC` | 12 | 0.29–0.59 | 0.6–1.2 GB |
| `ACHAF`, `CTPF`, `ACTPF` | 6 | 1.5–3.1 | 1.5–3.1 GB |
| `ACHTF` | 6 | 28 | 28 GB |
| `ACHAM`, `ACHTM`, `ACTPM`, one sector | 60 | 0.09–0.33 | 0.9–3.3 GB |

The largest single-channel files are channel 2, observed at 0.5 km. Reflective
channels compress less by day, so night hours are smaller: `MCMIPM` scenes were
3.0–3.8 MB in the 06:00 and 10:00 UTC hours that day. A day of `MCMIPF` is about
44 GB, and a week of CONUS channel 2 was already 122 GB before full disk was
supported. Run `usdata fetch --dry-run` first; it lists every file and totals
the bytes.

## Examples

Fetch one small shortwave-infrared CONUS scene (~255 kB):

```sh
uv run usdata fetch noaa:goes-abi \
  --start 2024-05-06T12:01:18.1Z --end 2024-05-06T12:01:18.1Z \
  -p satellite=18 -p channel=6
```

Fifteen minutes of one mesoscale channel (~4.93 MB in the verified window):

```sh
uv run usdata fetch noaa:goes-abi \
  --start 2024-05-06T22:00:00Z --end 2024-05-06T22:14:59.999999Z \
  -p satellite=16 -p channel=13 -p product=ABI-L2-CMIPM -p sector=M1
```

All 16 channels of one mesoscale scan in one file (4.5 MB), with no channel:

```sh
uv run usdata fetch noaa:goes-abi \
  --start 2024-05-06T22:00:28Z --end 2024-05-06T22:00:28Z \
  -p satellite=16 -p product=ABI-L2-MCMIPM -p sector=M1
```

Cloud-top phase for the same scan (87 kB):

```sh
uv run usdata fetch noaa:goes-abi \
  --start 2024-05-06T22:00:28Z --end 2024-05-06T22:00:28Z \
  -p satellite=16 -p product=ABI-L2-ACTPM -p sector=M1
```

The [walkthrough](https://usdata.dev/datasets/noaa-goes-abi/) opens a CONUS
channel and a 16-band mesoscale scene. The
[mesoscale example](https://usdata.dev/studies/goes-mesoscale/) checks scan
timing, quality flags, and footprint stability before comparing a fixed local
region, then restores all fifteen pinned scenes into an empty cache.

## Reading the files

Channel 6 is reflected solar imagery and the small CONUS example is mostly dark; it is
chosen to keep the live fetch/restore check small. For thermal imagery, CONUS channel
13 scenes are roughly 4 MB in the verified sample. CMI represents reflectance
for reflective bands or brightness temperature for infrared bands; consult the
file's units and data-quality flags before analysis. The adapter preserves raw
bytes and does not project, mask, or reinterpret imagery.

In an MCMIP file, channels 1 to 6 are reflectance factor (units `1`) and 7 to 16
are brightness temperature (K). Every channel is on the 2 km grid, so channels
1, 2, and 3, which NOAA observes at 1, 0.5, and 1 km, are coarser than in their
single-channel files. For the GOES-16 M1 scan starting 22:00:28 UTC on
2024-05-06, `CMI_C13` and `DQF_C13` equal `CMI` and `DQF` in the single-channel
`CMIPM1` channel-13 file value for value, and the live test checks this; other
channels were not compared. Stacking `CMI_C01` to `CMI_C16` gives a
`(16, y, x)` array without fetching or regridding 16 files. A file names its
satellite (`platform_ID`), scene (`scene_id`, with M1 or M2 in `dataset_name`),
and resolution (`spatial_resolution`), so assets carry no `properties`.

[NOAA's product documentation](https://www.ncei.noaa.gov/products/goes-terrestrial-weather-abi-glm)
identifies the products, their sectors, the channels, and scan modes. The
[NODD registry](https://registry.opendata.aws/noaa-goes/) documents public cloud
access. Satellite availability varies by date and outages; no East/West alias
is inferred from a historical query. The catalog's start is the initial public
GOES-16 date, not a claim that every satellite or product was operating then.
Listing `ABI-L2-CMIPC/2017/` with `max-keys=1` confirmed the first scene at
2017-02-28T00:02:50.4Z. The GOES-16 bucket also has placeholder year-2000 scenes
under the CMIP, MCMIP, ACTPC, and ACTPF directories, which NCEI's page describes as files
whose `s20000011200000` stamps may mean an incomplete scan. The adapter excludes
these by listing only from each product's first archived day and refusing
intervals entirely before it.

See the [service research notes](noaa-services.md#goes-abi-imagery-and-cloud-top-products)
for dated upstream probes.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Resolution: the [NCEI ABI and GLM product
  page](https://www.ncei.noaa.gov/products/goes-terrestrial-weather-abi-glm), whose
  channel table gives 0.5 km to 2 km nominal resolution by channel and an average
  five-minute scan frequency, and whose sector table gives full-disk files per day by
  mode: 96 in Mode 3, 288 in Mode 4, 144 in Mode 6, and 1,440 per day, one a minute,
  for each of the two mesoscale sectors. NESDIS's [geostationary satellites
  page](https://www.nesdis.noaa.gov/our-satellites/currently-flying/geostationary-satellites)
  says the imager scans as frequently as every 30 seconds. MCMIP's 2 km grid and
  the cloud-top products' 2, 4, and 10 km come from the `spatial_resolution` attribute
  of the fetched files, probed in the service notes.
- Products and sectors: the NCEI page's product type table, which lists ACHA, ACTP,
  CMIP, and MCMIP for M1, M2, C, and F, ACHT for M1, M2, and F, and CTP for C and F,
  as the bucket listings confirm.
- Updates, citation, and terms: the [NODD registry
  entry](https://registry.opendata.aws/noaa-goes/) and the [NOAA Open Data
  Dissemination](https://www.noaa.gov/information-technology/open-data-dissemination)
  statement it quotes.
- Variables: the file contents described on the NCEI page and carried by the fetched
  scenes; the MCMIP channel names and central wavelengths follow the NCEI channel table.
- Longest query window: `MAX_WINDOW` in `usdata.providers.noaa.goes`.
- Latency is empty: NODD says only that new data is added as soon as it is available,
  and the NCEI page's 30-minutes-to-two-hours figure describes CLASS subscriptions
  rather than this bucket.

[All NOAA datasets](noaa.md).

--8<-- "generated/catalog/noaa/goes-abi.md"
