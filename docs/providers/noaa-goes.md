# GOES ABI CONUS imagery

Available since v0.8 as `noaa:goes-abi`. The initial product is
single-channel CONUS Cloud and Moisture Imagery, `ABI-L2-CMIPC`. Files are
NetCDF4/HDF5 scenes from the anonymous `noaa-goes16`, `noaa-goes17`,
`noaa-goes18`, and `noaa-goes19` buckets. No AWS credentials or SDK are needed.
Other ABI products and scan sectors remain unsupported.

Require `satellite` (16, 17, 18, or 19), `channel` (1–16, also `C01`–`C16`),
and both timestamps. `product` defaults to `ABI-L2-CMIPC` and rejects any other
value. Unknown parameters, text/geographic constraints, and `variables` are rejected:
channels select distinct whole files; the server cannot crop these scenes or
select variables within them. `temporal_subset` means selecting archived scans.

The adapter lists hourly `ABI-L2-CMIPC/YYYY/DDD/HH/` prefixes, follows S3
continuation tokens, and selects scans whose **start times** fall in the inclusive
UTC query interval. It does not select a scan that started before the interval
merely because the scan overlaps it. Filename start/end stamps have tenths-of-a-
second precision; asset metadata retains both bounds and the listed byte size.
Naive dates/times mean UTC; a date-only end is midnight at the start of that day.
Use a short interval to limit the number of whole-scene downloads.

For example, fetch one small shortwave-infrared scene (~255 kB):

```sh
uv run usdata fetch noaa:goes-abi \
  --start 2024-05-06T12:01:18.1Z --end 2024-05-06T12:01:18.1Z \
  -p satellite=18 -p channel=6
```

Channel 6 is reflected solar imagery and this example is mostly dark; it is
chosen to keep the live fetch/restore check small. For thermal imagery, channel
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

[All NOAA datasets](noaa.md).
