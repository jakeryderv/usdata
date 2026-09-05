# Weather and streamflow inputs

Fetch two days of station weather near Oklahoma City and streamflow at the
USGS Tulsa site. This example demonstrates collecting and preserving inputs;
it does not infer a causal relationship between the two sites.

Requires usdata v0.5 or newer. To run the bundled example, follow
[development setup](../../README.md#development), then run from the repo root:

```sh
uv run usdata pull examples/weather-and-streamflow/dataset.yaml --cache-dir /tmp/usdata-example
uv run usdata verify examples/weather-and-streamflow/dataset.yaml --cache-dir /tmp/usdata-example
uv run usdata pull examples/weather-and-streamflow/dataset.yaml --cache-dir /tmp/usdata-example
```

Use a cache path of your choice (for example a temporary directory on Windows).
The first command should fetch two CSV assets and write
`examples/weather-and-streamflow/dataset.lock.json`. The second reports
`all assets match dataset.lock.json`. The third reports both assets as `cached`
and says it restored from the lockfile.

The NOAA CSV includes `DATE`, `PRCP`, and `TMAX`. The USGS CSV has two daily
rows with `monitoring_location_id`, `parameter_code`, `value`, `unit_of_measure`,
and quality metadata. Filenames and checksums depend on the precise queries
and returned bytes, so they are not hardcoded here.

To test restoration, delete one downloaded CSV from your example cache and
run pull again. It should fetch that file and verify its original checksum.
If upstream has changed, the mismatch is reported instead. Preserve the cache
if you need an archive; keep your own manifest and lockfile in your analysis repo.
The generated example lockfile is ignored in this SDK checkout.

The complete [manifest reference](../../docs/reference/manifests.md) explains
empty sources, provider parameters, time semantics, `--force`, and failure codes.
