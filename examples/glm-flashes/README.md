# Lightning flashes around a reported tornado

Available since v0.15.0. The [manifest](dataset.yaml) requests one hour of
GOES-16 Geostationary Lightning Mapper detections through `noaa:goes-glm`,
starting at 20:00 UTC on 2024-05-06. That is the hour around the Oklahoma
Storm Events report used by the
[event context example](https://usdata.dev/examples/event-context/). GLM writes
one file every 20 seconds, so the hour is 180 files of roughly 300 kB each,
about 55 MB in total. Each file covers the satellite's whole field of view;
the manifest cannot crop to Oklahoma, so the snippet below does that locally.

In an activated Python 3.11+ virtual environment, install the published package
with the NetCDF reader and pandas, and save the [manifest](dataset.yaml) as
`dataset.yaml` in a working directory. Run the commands from that directory:

```sh
python -m pip install "usdata[netcdf,pandas]"
usdata pull dataset.yaml
usdata verify dataset.yaml
```

Count the flashes near Oklahoma City minute by minute. Run this with `python`
in the same directory and environment:

```python
from pathlib import Path

import pandas as pd
from usdata import pull, verify

manifest = Path("dataset.yaml")
columns = ["flash_time_offset_of_first_event", "flash_lat", "flash_lon", "flash_energy"]
tables = []
for item in pull(manifest).fetched:
    detections = item.open()
    tables.append(detections[columns].reset_coords(drop=True).to_dataframe())
flashes = pd.concat(tables, ignore_index=True)
near = flashes[flashes.flash_lat.between(34.5, 36.5) & flashes.flash_lon.between(-98.5, -96.5)]
per_minute = near.groupby(near.flash_time_offset_of_first_event.dt.floor("min")).size()
print(per_minute.to_string())
print(f"{len(near)} of {len(flashes)} flashes within the box")
assert verify(manifest) == []
```

For a [source installation](https://docs.usdata.dev/install/#source-installation), run from
`examples/glm-flashes/` and use `uv run usdata` and `uv run python`.

Flash times are the first constituent event's time and can precede a file's
nominal start by a fraction of a second, which is why the snippet groups by the
decoded times rather than by file. The box is a two-degree square of latitude
and longitude, not a storm outline, and a count of flashes is not a measure of
storm intensity on its own. See [NOAA access notes](https://docs.usdata.dev/providers/noaa-glm/)
for the file layout, the one-day query limit, and the flash, group, and event
tables.
