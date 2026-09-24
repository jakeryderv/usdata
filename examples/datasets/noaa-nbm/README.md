# How warm did the National Blend expect Oklahoma City to stay through the evening of 6 May 2024?

Available since v0.20.0. The [manifest](dataset.yaml) asks the National Blend
of Models for the first four hours of its 20 UTC run on 2024-05-06 through
`noaa:nbm`, and for one field of each: the 2 m temperature, named as the
object's index sidecar names it. Each CONUS file is 171 MB; the fetch reads
each index and asks S3 for one byte range of about 1.5 MB, and the lockfile
pins four ranges and four ETags. The blend is guidance, not a model run: it
combines many models and corrects their biases, so it is what a forecaster
would have started from that afternoon.

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

Print the forecast temperature at the grid point nearest Oklahoma City for
each valid hour. Run this with `python` in the same directory and environment:

```python
from pathlib import Path

import numpy as np
from usdata import pull, verify

manifest = Path("dataset.yaml")
result = pull(manifest)
for item in result.by_source["forecast"]:
    fields = item.open()
    (name,) = fields.data_vars
    latitude = fields.latitude.values
    longitude = fields.longitude.values
    longitude = np.where(longitude > 180, longitude - 360, longitude)
    distance = (latitude - 35.47) ** 2 + (longitude + 97.52) ** 2
    y, x = np.unravel_index(np.argmin(distance), latitude.shape)
    celsius = float(fields[name][y, x]) - 273.15
    valid = item.asset.time.start
    where = f"{latitude[y, x]:.3f}N {longitude[y, x]:.3f}E"
    print(f"valid {valid:%Y-%m-%d %H:%M} UTC: {celsius:.1f} C at {where}")
assert verify(manifest) == []
```

For a [source installation](https://docs.usdata.dev/install/#source-installation), run from
`examples/datasets/noaa-nbm/` and use `uv run usdata` and `uv run python`.

`by_source["forecast"]` comes back in valid-time order, so the loop prints
21 UTC through 00 UTC. Each file is one message and opens without `select`;
the variable is `2t` in kelvin, converted here. The 2.5 km grid is Lambert
conformal, so the nearest point is found in two-dimensional coordinates. Later
forecast hours thin out to every 3 and then every 6 hours on a schedule that
varies by cycle; an hour the run does not publish is named after the listing.

Keep the manifest, lockfile, and cached bytes together. A republished object
refuses the pinned ETag and is reported as drift; `pull --update` accepts the
new ranges. Query details are in the
[NBM guide](https://docs.usdata.dev/providers/noaa-nbm/).

## What was awkward

- The 171 MB CONUS file makes `messages` the only sensible way in, but the
  index vocabulary has to be discovered from the sidecar itself: NBM lines
  carry a fourth field for ensemble spread and probability thresholds, and
  nothing in `usdata info` says which selectors a dataset's files hold. The
  guide's table is the substitute for a listing of the index.
