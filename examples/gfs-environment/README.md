# Global model environment before a reported tornado

Available since v0.15.0. The [manifest](dataset.yaml) requests the GFS 00 UTC
1 degree analysis for 2024-05-06 through `noaa:gfs`: forecast hour 0 of the
`pgrb2.1p00` file, valid at the initialization time, 28 hours 39 minutes
(28.65 hours) before the Oklahoma Storm Events report used by the
[event context example](https://usdata.dev/examples/event-context/) and the
[HRRR example](https://usdata.dev/examples/hrrr-environment/) that reads the
20 UTC analysis. A pre-convective analysis that old is not concurrent with the
event: it describes the air mass the day before, and verifies nothing about the
environment at 2024-05-07T04:39:00Z. The file is one whole global grid of 696 fields, about 42 MB;
the manifest cannot subset it, so the snippet below selects fields after the
download.

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
y = int(np.argmin(np.abs(cape.latitude.values - 35.47)))
x = int(np.argmin(np.abs(cape.longitude.values - (-97.52 % 360))))
(cape_name,) = cape.data_vars
(helicity_name,) = helicity.data_vars
print(f"grid point {float(cape.latitude[y]):.1f}N {float(cape.longitude[x]) - 360:.1f}E")
print(f"surface CAPE {float(cape[cape_name][y, x]):.0f} J/kg")
print(f"0-3 km helicity {float(helicity[helicity_name][y, x]):.0f} m2/s2")
assert verify(manifest) == []
```

For a [source installation](https://docs.usdata.dev/install/#source-installation), run from
`examples/gfs-environment/` and use `uv run usdata` and `uv run python`.

The analysis is the model's estimate at 00 UTC, not an observation, and one
grid point is a 1 degree cell about 100 km across, not the storm's inflow; the
0.25 degree files give a finer grid at twelve times the size. GFS longitudes
use the 0–360 convention, which the snippet handles when it finds the nearest
point. See [NOAA access notes](https://docs.usdata.dev/providers/noaa-gfs/)
for cycles, forecast hours, resolutions, and the field selection keys.
