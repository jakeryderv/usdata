# Derived radar products around a tornado report

Available since v0.15. The [manifest](dataset.yaml) requests thirty minutes of
NEXRAD Level III products from the Oklahoma City radar (`KTLX`) on 2024-05-06
through `noaa:nexrad-level3`: mesocyclone detections (`NMD`), storm tracking
information (`NST`), and enhanced echo tops (`EET`) from 20:30 to 21:00 UTC.
That is the hour of the [event-context notebook](https://usdata.dev/studies/event-context/),
which pairs a Storm Events tornado report with a Level II volume and a GOES
scene. Every file is one product for one volume scan. The detection products
for this radar begin at 20:42 UTC that day although reflectivity is continuous:
the bucket holds what the Unidata feed captured, and a missing scan is a gap in
the archive rather than an error.

In an activated Python 3.11+ virtual environment, install the published package
and save the [manifest](dataset.yaml) as `dataset.yaml` in a working directory.
Run the commands from that directory:

```sh
python -m pip install usdata
usdata pull dataset.yaml
usdata verify dataset.yaml
```

The pull lists each product's flat keys for the day, keeps the scans inside the
window, downloads them whole, and writes `dataset.lock.json`. List what arrived
with `python` in the same directory and environment:

```python
from pathlib import Path

from usdata import pull, verify
from usdata.readers import UnsupportedFormat

manifest = Path("dataset.yaml")
result = pull(manifest)
for item in result.fetched:
    site, product, *stamp = item.asset.id.split("_")
    print(product, "-".join(stamp[:3]), ":".join(stamp[3:]), item.path.stat().st_size, "bytes")
try:
    result.fetched[0].open()
except UnsupportedFormat as error:
    print(error)
assert verify(manifest) == []
```

Level III has no usdata reader in this release, which is what the caught error
says. Decode a cached file with [Py-ART](https://arm-doe.github.io/pyart/)
if you need its contents:

```python
import pyart

radar = pyart.io.read_nexrad_level3(result.fetched[0].path)
print(radar.fields.keys())
```

For a [source installation](https://docs.usdata.dev/install/#source-installation), run from
`examples/datasets/noaa-nexrad-level3/` and use `uv run usdata` and `uv run python`.

The mesocyclone product is about 150 bytes when the algorithm found nothing and
a few kilobytes when it did; a small file is a valid, empty detection table, not
a failed download. Product timestamps are the radar's volume scan times in
UTC. See [NOAA access notes](https://docs.usdata.dev/providers/noaa-nexrad-level3/)
for product codes, sizes, and the archive's 2020-03-30 start.
