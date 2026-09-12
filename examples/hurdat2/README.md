# Atlantic hurricane best tracks

Available from source for the unreleased v0.12.0. The [manifest](dataset.yaml)
requests the complete Atlantic HURDAT2 best-track file through `noaa:hurdat2`.
The National Hurricane Center publishes one fixed-format text file per basin and
revises it after each season, so the manifest names a basin and nothing else:
dates and geographic filters are rejected rather than silently ignored.

In an activated Python 3.11+ virtual environment, install the package and save
the [manifest](dataset.yaml) as `dataset.yaml` in a working directory. Run the
commands from that directory:

```sh
python -m pip install "usdata[pandas]"
usdata pull dataset.yaml
usdata verify dataset.yaml
```

The Atlantic file is about 7 MB of text; the Pacific file
(`basin: pacific`) is about 4 MB. Open it locally with the HURDAT2 reader, which
`item.open()` selects without arguments. Run this with `python` in the same
directory and environment:

```python
from pathlib import Path

from usdata import pull, verify

manifest = Path("dataset.yaml")
result = pull(manifest)
(item,) = result.fetched
tracks = item.open()
landfalls = tracks[(tracks.record_identifier == "L") & (tracks.status == "HU")]
print(len(tracks), "track points;", len(landfalls), "hurricane-intensity landfall records")
print(tracks.loc[tracks.max_wind_kt.idxmax(), ["storm_id", "name", "time", "max_wind_kt"]])
assert verify(manifest) == []
```

For a [source installation](https://docs.usdata.dev/project/#source-installation), run from
`examples/hurdat2/` and use `uv run usdata` and `uv run python`.

The reader returns one row per best-track point: `storm_id`, `name`, UTC `time`,
`record_identifier`, `status`, signed `latitude`/`longitude`, `max_wind_kt`,
`min_pressure_mb`, twelve wind-radii columns, and `max_wind_radius_nm`. The
documented missing sentinels become NaN (`-999`, and `-99` where a maximum wind
was left unassigned on a non-developing depression). Wind radii are absent
before 2004, and the radius of maximum wind is mostly NaN before 2021: the
Atlantic file back-fills it for a few hundred earlier points, chiefly reanalyzed
landfalls, while the Pacific file has none. A landfall row is not one
landfall event per storm, and a track point is not an observation: HURDAT2 is a
post-season reanalysis whose early decades undercount storms and underestimate
intensities. Compare eras with that in mind.

A repeat pull uses the lockfile and checksummed cache. Keep the manifest,
lockfile, and cached bytes for reproducibility: the NHC replaces this file with
a newly named revision each season, and an old checksum cannot recreate a file
that is no longer published. Use `pull(manifest, force=True)` when deliberately
moving to the current revision. See
[NOAA access notes](https://docs.usdata.dev/providers/noaa-hurdat2/)
for revision selection, basin naming, and format limits.
