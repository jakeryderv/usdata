# Annual airport climate

Available from source for v0.10. The [manifest](dataset.yaml)
requests one year of precipitation and mean temperature at Will Rogers World
Airport through `noaa:gsoy`. GSOY selects every UTC calendar year touched by the
query in full; May 6–7 selects all of 2024, while December 31–January 1 selects
both years.

Complete the [source installation](../../README.md#source-installation), then
from the repository root:

```sh
uv run usdata pull examples/annual-climate/dataset.yaml
uv run usdata verify examples/annual-climate/dataset.yaml
```

Open the downloaded CSV locally with the same generic reader used by other
station datasets. Run this with `uv run python`:

```python
from usdata import pull, verify

manifest = "examples/annual-climate/dataset.yaml"
result = pull(manifest)
(item,) = result.fetched
frame = item.open(dtype={"DATE": "string"})
print(frame[["STATION", "DATE", "PRCP", "TAVG"]])
assert verify(manifest) == []
```

`DATE` is a four-digit year label. Explicit `dtype` keeps numeric-looking labels
as text; no datetime parsing or provider-specific reader is needed. The request
uses metric units: `PRCP` is annual precipitation in millimeters and `TAVG` is
annual mean temperature in degrees Celsius. NCEI CSV has no units row, so the
reader retains request provenance rather than synthesizing a units map.

A repeat pull uses the lockfile and checksummed cache. Keep the manifest,
lockfile, and cached bytes for reproducibility: NCEI revises records, and an old
checksum cannot recreate data that is no longer available upstream. Annual
labels do not imply identical accumulation seasons for every element; consult
[NOAA access notes](../../docs/providers/noaa-gsoy.md)
when choosing other variables.
