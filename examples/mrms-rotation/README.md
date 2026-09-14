# Rotation tracks around a reported tornado

Available since v0.15.0. The [manifest](dataset.yaml) requests twenty minutes
of MRMS mid-level rotation tracks through `noaa:mrms`, from 04:30 to 04:50 UTC
on 2024-05-07, around Oklahoma Storm Events tornado report 1184052 (22:39 CST
on May 6), the case used by the
[event context](https://usdata.dev/examples/event-context/) and
[tornado classification](https://usdata.dev/examples/tornado-classification/)
examples. MRMS
writes one file every two minutes, so the window is eleven files of roughly
100 kB each, about 1 MB in total. Each file is the whole CONUS grid; the
manifest cannot crop to Oklahoma, so the snippet below does that locally.

In an activated Python 3.11+ virtual environment, install the published package
with the GRIB2 reader and save the [manifest](dataset.yaml) as `dataset.yaml`
in a working directory. Run the commands from that directory:

```sh
python -m pip install "usdata[grib]"
usdata pull dataset.yaml
usdata verify dataset.yaml
```

Find the strongest mid-level rotation near Oklahoma City in each file. Run this
with `python` in the same directory and environment:

```python
from pathlib import Path

import numpy as np
from usdata import pull, verify

manifest = Path("dataset.yaml")
for item in pull(manifest).fetched:
    grid = item.open()
    (name,) = list(grid.data_vars)
    shear = grid[name].sel(latitude=slice(35.8, 35.0), longitude=slice(262.0, 263.0))
    values = shear.where(shear >= 0)
    peak = values.max().item()
    where = values.argmax(dim=("latitude", "longitude"))
    lat = float(values.latitude[where["latitude"]])
    lon = float(values.longitude[where["longitude"]]) - 360
    stamp = item.asset.time.start.strftime("%H:%M")
    print(f"{stamp}  peak {peak:6.1f} (0.001/s) at {lat:.3f}N {lon:.3f}E")
assert verify(manifest) == []
```

For a [source installation](https://docs.usdata.dev/project/#source-installation), run from
`examples/mrms-rotation/` and use `uv run usdata` and `uv run python`.

Longitudes in MRMS grids run 230° to 300° east, so the box is selected in that
frame and printed in the usual negative-west form. Latitudes decrease down the
grid, which is why the latitude slice runs north to south. Negative values are
the source's no-coverage and no-data sentinels, masked before the maximum. A
rotation-track maximum is azimuthal shear accumulated over the trailing 30
minutes, not a tornado detection; see [NOAA access notes](https://docs.usdata.dev/providers/noaa-mrms/)
for the product list, the one-day query limit, and memory needs.
