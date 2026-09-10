# Coastal water levels

Available since v0.10.0. This small manifest requests three historical
six-minute observations at The Battery, New York, relative to mean lower low
water (MLLW), in meters and UTC. It does not request tide predictions.

In an activated Python 3.11+ virtual environment, install the published package
and save the [manifest](dataset.yaml) as `dataset.yaml` in a working directory.
Run the commands from that directory:

```sh
python -m pip install "usdata[pandas]"
usdata pull dataset.yaml
usdata verify dataset.yaml
```

Run the following with `python` in the same directory and environment:

```python
from pathlib import Path

import pandas as pd
from usdata import pull

result = pull(Path("dataset.yaml"))
item = result.fetched[0]
frame = item.open().rename(columns=str.strip)
frame["Date Time"] = pd.to_datetime(frame["Date Time"], utc=True)
print(frame[["Date Time", "Water Level", "Quality"]])
print(item.provenance.source_url)
```

For a [source installation](../../README.md#source-installation), run from
`examples/coastal-water-levels/` and use `uv run usdata` and `uv run python`.

The CSV reader preserves original column names, including NOAA's spaces. The
local rename above makes them easier to use; it does not modify cached bytes.
The requested station, datum, units, and timezone are recorded in the source URL,
not embedded as separate CSV columns. Metric heights are meters; English heights
are feet. A different datum changes the reference elevation, not just the units.

Keep `Quality` with the original flag columns. `v` means verified and `p` means
preliminary; flag meanings differ between these states. The first flag's header
is `O or I (for verified)`. Consult the [official field definitions](https://api.tidesandcurrents.noaa.gov/api/prod/responseHelp.html)
before filtering observations. Gaps and missing measurements are not filled.

Both timestamps must have minute precision and span at most 28 days. Longer
requests can be declared as separate manifest sources. Date-only bounds mean
midnight UTC, not the end of a calendar day. Empty or invalid API responses raise
an upstream error during fetching, including NOAA's HTTP-200 no-data message;
`allow_empty` only applies to empty resolution and does not suppress that error.

Preserve the manifest, lockfile, and cache together. Locked restoration checks
exact bytes; upstream revisions require an explicit refresh rather than silently
changing the analysis inputs. See [NOAA access notes](../../docs/providers/noaa-coops.md)
for supported parameters and limits.
