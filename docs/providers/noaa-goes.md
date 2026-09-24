# GOES ABI CONUS and mesoscale imagery

Available since v0.8 as `noaa:goes-abi`. The initial product is
single-channel CONUS Cloud and Moisture Imagery, `ABI-L2-CMIPC`. Files are
NetCDF4/HDF5 scenes from the anonymous `noaa-goes16`, `noaa-goes17`,
`noaa-goes18`, and `noaa-goes19` buckets. No AWS credentials or SDK are needed.
Mesoscale imagery is available since v0.25.0. Select
`product=ABI-L2-CMIPM` and explicitly name `sector=M1` or `sector=M2`.
Full-disk imagery and other ABI products remain unsupported.

Require `satellite` (16, 17, 18, or 19), `channel` (1–16, also `C01`–`C16`),
and both timestamps. `product` defaults to `ABI-L2-CMIPC`, which accepts no
`sector`; `ABI-L2-CMIPM` requires one of the two mesoscale sectors. Missing or
conflicting selectors fail before network access. Unknown parameters,
text/geographic constraints, and `variables` are rejected:
channels select distinct whole files; the server cannot crop these scenes or
select variables within them. `temporal_subset` means selecting archived scans.

The adapter lists hourly `PRODUCT/YYYY/DDD/HH/` prefixes, follows S3
continuation tokens, and selects scans whose **start times** fall in the inclusive
UTC query interval. It does not select a scan that started before the interval
merely because the scan overlaps it. Filename start/end stamps have tenths-of-a-
second precision; asset metadata retains both bounds and the listed byte size.
A query spans at most seven days; split longer intervals. Even a week of one
CONUS channel is about 2,000 whole scenes; mesoscale scans are more frequent,
so keep intervals short and inspect the dry-run byte estimate before fetching.

Both mesoscale sectors share the `ABI-L2-CMIPM` directory; filenames distinguish
`CMIPM1` from `CMIPM2`. The adapter filters the requested sector, channel, and
satellite, never mixing M1 and M2. A sector is a movable observation window,
not a geographic alias. Inspect the coordinates and `geospatial_lat_lon_extent`
in every file before comparing pixels across time; scan-start seconds and sector
coverage can change. No sector-by-location selection is inferred.

--8<-- "_snippets/utc-window.md"

For example, fetch one small shortwave-infrared scene (~255 kB):

```sh
uv run usdata fetch noaa:goes-abi \
  --start 2024-05-06T12:01:18.1Z --end 2024-05-06T12:01:18.1Z \
  -p satellite=18 -p channel=6
```

For fifteen minutes of one mesoscale sector (~4.93 MB in the verified window):

```sh
uv run usdata fetch noaa:goes-abi \
  --start 2024-05-06T22:00:00Z --end 2024-05-06T22:14:59.999999Z \
  -p satellite=16 -p channel=13 -p product=ABI-L2-CMIPM -p sector=M1
```

The [mesoscale example](https://usdata.dev/studies/goes-mesoscale/) checks scan
timing, quality flags, and footprint stability before comparing a fixed local
region, then restores all fifteen pinned scenes into an empty cache.

Channel 6 is reflected solar imagery and the small CONUS example is mostly dark; it is
chosen to keep the live fetch/restore check small. For thermal imagery, CONUS channel
13 scenes are roughly 4 MB in the verified sample. CMI represents reflectance
for reflective bands or brightness temperature for infrared bands; consult the
file's units and data-quality flags before analysis. The adapter preserves raw
bytes and does not project, mask, or reinterpret imagery.

[NOAA's product documentation](https://www.ncei.noaa.gov/products/goes-terrestrial-weather-abi-glm)
identifies CMIP channels, scan modes, and satellite coverage. The
[NODD registry](https://registry.opendata.aws/noaa-goes/) documents public cloud
access. Satellite availability varies by date and outages; no East/West alias
is inferred from a historical query. The catalog's start is the initial public
GOES-16 date, not a claim that every satellite was operating then. Listing
`ABI-L2-CMIPC/2017/` with `max-keys=1` confirmed the first scene at
2017-02-28T00:02:50.4Z. The bucket also has placeholder year-2000 test scenes;
the adapter excludes these by limiting selection to the public observation era
and rejecting intervals entirely before 2017-02-28.


See the [service research notes](noaa-services.md#goes-abi-conus-imagery) for dated upstream probes.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Resolution: the [NCEI ABI and GLM product
  page](https://www.ncei.noaa.gov/products/goes-terrestrial-weather-abi-glm), which
  gives 0.5 km to 2 km spatial resolution for the ABI radiances CMIP derives from and an
  average five-minute scan frequency. The [ABI scan-mode documentation](https://goes-r.noaa.gov/users/abiScanModeInfo.html)
  gives two mesoscale sectors every 60 seconds or one every 30 seconds.
- Updates, citation, and terms: the [NODD registry
  entry](https://registry.opendata.aws/noaa-goes/) and the [NOAA Open Data
  Dissemination](https://www.noaa.gov/information-technology/open-data-dissemination)
  statement it quotes.
- Variables: the CMIP file contents described on the NCEI page and carried by the
  fetched scenes.
- Longest query window: `MAX_WINDOW` in `usdata.providers.noaa.goes`.
- Latency is empty: NODD says only that new data is added as soon as it is available,
  and the NCEI page's 30-minutes-to-two-hours figure describes CLASS subscriptions
  rather than this bucket.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/goes-abi.md#catalog-reference).
