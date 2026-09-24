# What did the 13 km RAP analysis say about the storm environment over Oklahoma City at 20 UTC?

Available since v0.20.0. The [manifest](dataset.yaml) asks the Rapid Refresh
for its 20 UTC analysis of 2024-05-06 through `noaa:rap`, and for two fields
of it: surface-based CAPE and 0–3 km storm-relative helicity, named as the
object's index sidecar names them. The fetch reads that index and asks S3 for
the two byte ranges, about 80 KB of an 18 MB file, and the lockfile pins the
ranges and the object's ETag. The
[HRRR example](https://usdata.dev/datasets/noaa/hrrr/) reads the same
two fields from the 3 km model at the same hour; this one is the coarser
parent, with a grid point every 13.5 km.

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

Read both fields at the grid point nearest Oklahoma City. Run this with
`python` in the same directory and environment:

```python
from pathlib import Path

import numpy as np
from usdata import pull, verify

manifest = Path("dataset.yaml")
result = pull(manifest)
fields = result.one("environment").open()
latitude = fields.latitude.values
longitude = fields.longitude.values
longitude = np.where(longitude > 180, longitude - 360, longitude)
distance = (latitude - 35.47) ** 2 + (longitude + 97.52) ** 2
y, x = np.unravel_index(np.argmin(distance), latitude.shape)
print(f"grid point {latitude[y, x]:.2f}N {longitude[y, x]:.2f}E")
for name in fields.data_vars:
    print(f"{name}: {float(fields[name][y, x]):.0f} {fields[name].attrs['units']}")
assert verify(manifest) == []
```

For a [source installation](https://docs.usdata.dev/install/#source-installation), run from
`examples/datasets/noaa-rap/` and use `uv run usdata` and `uv run python`.

The file fetched with `messages` is already a selection, so it opens without
`select`, and the two variables are named after the fields the messages hold.
The grid is Lambert conformal, so `latitude` and `longitude` are
two-dimensional and the nearest point is found in both. The analysis is the
model's estimate at 20 UTC, eight and a half hours before the report the
[severe-weather case study](https://usdata.dev/studies/severe-weather-case-study/)
studies, and a 13 km cell is not the storm's inflow.

Keep the manifest, lockfile, and cached bytes together. A republished object
refuses the pinned ETag and is reported as drift; `pull --update` accepts the
new ranges. Query details are in the
[RAP guide](https://docs.usdata.dev/providers/noaa-rap/).

## What was awkward

- The nearest grid point on a Lambert grid takes four lines of NumPy in every
  model example, and the 0–360 longitude convention has to be undone by hand
  first. The examples document the idiom because the roadmap keeps
  nearest-grid-point helpers out of scope as analysis; it is the most repeated
  thing the examples do.
