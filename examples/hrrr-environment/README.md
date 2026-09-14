# Model environment around a reported tornado

Available since v0.15.0. The [manifest](dataset.yaml) requests the HRRR 20 UTC
analysis for 2024-05-06 through `noaa:hrrr`: forecast hour 0 of the surface
file, valid at the initialization time. That is the hour of the Oklahoma
Storm Events report used by the
[event context example](https://usdata.dev/examples/event-context/). The file
is one whole CONUS grid of 170 fields, about 150 MB; the manifest cannot
subset it, so the snippet below selects fields after the download.

In an activated Python 3.11+ virtual environment, install the published package
with the GRIB2 reader, and save the [manifest](dataset.yaml) as `dataset.yaml`
in a working directory. Run the commands from that directory:

```sh
python -m pip install "usdata[grib]"
usdata pull dataset.yaml
usdata verify dataset.yaml
```

The `grib` extra installs with pip alone on Linux and on Windows through
Python 3.13; macOS needs the ecCodes library from conda-forge or Homebrew
first. See the [reader reference](https://docs.usdata.dev/reference/readers/).

Read surface-based CAPE and 0–3 km storm-relative helicity at the grid point
nearest Oklahoma City. Run this with `python` in the same directory and
environment:

```python
from pathlib import Path

import numpy as np
from usdata import pull, verify

manifest = Path("dataset.yaml")
(item,) = pull(manifest).fetched
cape = item.open(select={"shortName": "cape", "typeOfLevel": "surface"})
helicity = item.open(
    select={"shortName": "hlcy", "typeOfLevel": "heightAboveGroundLayer", "level": 3000}
)
distance = (cape.latitude - 35.47) ** 2 + ((cape.longitude % 360) - (-97.52 % 360)) ** 2
y, x = np.unravel_index(int(distance.argmin()), distance.shape)
(cape_name,) = cape.data_vars
(helicity_name,) = helicity.data_vars
print(f"grid point {float(cape.latitude[y, x]):.3f}N {float(cape.longitude[y, x]) - 360:.3f}E")
print(f"surface CAPE {float(cape[cape_name][y, x]):.0f} J/kg")
print(f"0-3 km helicity {float(helicity[helicity_name][y, x]):.0f} m2/s2")
assert verify(manifest) == []
```

For a [source installation](https://docs.usdata.dev/install/#source-installation), run from
`examples/hrrr-environment/` and use `uv run usdata` and `uv run python`.

The analysis is the model's estimate at 20 UTC, not an observation, and one
grid point is a 3 km cell, not the storm's inflow. HRRR longitudes are stored
in the 0–360 convention, which the snippet handles when it finds the nearest
point. See [NOAA access notes](https://docs.usdata.dev/providers/noaa-hrrr/)
for cycles, forecast hours, file variants, and the field selection keys.
