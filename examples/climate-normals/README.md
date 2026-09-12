# Monthly climate normals

Available since v0.11.0. The [manifest](dataset.yaml)
requests 1991-2020 monthly normals of maximum temperature, minimum temperature,
and precipitation at Will Rogers World Airport through `noaa:climate-normals`.
Normals are 30-year averages, so the source needs no dates; `period: monthly`
selects the monthly dataset and the whole year is requested.

In an activated Python 3.11+ virtual environment, install the published package
and save the [manifest](dataset.yaml) as `dataset.yaml` in a working directory.
Run the commands from that directory:

```sh
python -m pip install "usdata[pandas]"
usdata pull dataset.yaml
usdata verify dataset.yaml
```

Open the downloaded CSV with the generic pandas reader and compare an observed
month against its normal. Run this with `python` in the same directory and environment:

```python
from pathlib import Path

from usdata import pull, verify

manifest = Path("dataset.yaml")
(item,) = pull(manifest).fetched
normals = item.open(dtype={"DATE": "string"}).set_index("DATE")
print(normals[["MLY-TMAX-NORMAL", "MLY-TMIN-NORMAL", "MLY-PRCP-NORMAL"]])
may = normals.loc["05"]
print(
    f"May normal: high {may['MLY-TMAX-NORMAL']:.1f} C, "
    f"low {may['MLY-TMIN-NORMAL']:.1f} C, precipitation {may['MLY-PRCP-NORMAL']:.1f} mm"
)
assert verify(manifest) == []
```

For a [source installation](https://docs.usdata.dev/project/#source-installation), run from
`examples/climate-normals/` and use `uv run usdata` and `uv run python`.

`DATE` is the two-digit month; explicit `dtype` keeps it as text. Metric units
give degrees Celsius and millimeters. To compare with observations, pull the
same station and month through `noaa:gsom` as in the
[monthly climate notebook](https://usdata.dev/examples/monthly-climate/) and subtract the
normal from the observed value to get the monthly anomaly. The
[climate anomalies notebook](https://usdata.dev/examples/climate-anomalies/) does this for a
full year and handles `MLY-TAVG-NORMAL`, which NCEI returns in degrees
Fahrenheit even under `units: metric`.

For daily normals, set `period: daily` and optionally `start` and `end` to keep
a month-day window; the year is ignored. See the
[NOAA access notes](https://docs.usdata.dev/providers/noaa-normals/) for
variable codes, units, and limitations. Keep the manifest, lockfile, and cached
bytes together: normals are corrected occasionally, and a checksum cannot
recreate bytes that upstream no longer serves.
