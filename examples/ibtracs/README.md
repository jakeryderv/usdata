# Which tropical cyclones reached Category 4 or 5 worldwide in recent seasons?

Available since v0.20.0. The [manifest](dataset.yaml) requests the IBTrACS
`last3years` file through `noaa:ibtracs`: every basin's best tracks for the
current season and the three before it, merged by NCEI from the responsible
agencies into one CSV of about 10 MB. IBTrACS publishes whole files and no query
interface, so the manifest names a subset and nothing else: dates and
geographic filters are rejected rather than silently ignored.

In an activated Python 3.11+ virtual environment, install the package and save
the [manifest](dataset.yaml) as `dataset.yaml` in a working directory. Run the
commands from that directory:

```sh
python -m pip install "usdata[pandas]"
usdata pull dataset.yaml
usdata verify dataset.yaml
```

The CSV lays a units row under its header, so `item.open()` selects the
units-row reader without arguments and keeps the units in `attrs["units"]`.
Run this with `python` in the same directory and environment:

```python
from pathlib import Path

from usdata import pull, verify

manifest = Path("dataset.yaml")
result = pull(manifest)
tracks = result.one("tracks").open(parse_dates=["ISO_TIME"])
units = tracks.attrs["units"]
print(len(tracks), "track points;", tracks.SID.nunique(), "storms; wind in", units["USA_WIND"])
print(tracks.groupby(["SEASON", "TRACK_TYPE"]).SID.nunique().unstack(fill_value=0))
peak = tracks.groupby(["SID", "NAME", "SEASON", "TRACK_TYPE"], as_index=False).agg(
    basin=("BASIN", "first"), category=("USA_SSHS", "max"), wind_kt=("USA_WIND", "max")
)
majors = peak[peak.category >= 4].sort_values(["SEASON", "wind_kt"], ascending=[True, False])
print(majors.groupby("SEASON").size().to_dict(), "storms of category 4 or 5 per season")
print(majors.head(8).to_string(index=False))
assert verify(manifest) == []
```

For a [source installation](https://docs.usdata.dev/install/#source-installation), run from
`examples/ibtracs/` and use `uv run usdata` and `uv run python`.

The table has one row per three-hourly track point and 174 columns: the
storm's serial id, season, basin, and name; the position and the responsible
WMO agency's wind and pressure; then each agency's own report in its own
columns, of which the U.S. set (`USA_WIND`, `USA_PRES`, `USA_SSHS`, the wind
radii) is the most complete. The single space IBTrACS writes for a missing
value is read as missing, and the North Atlantic basin code `NA` stays text
rather than becoming missing as pandas would otherwise read it.

Read `TRACK_TYPE` before comparing seasons. A season is `main` once the
responsible agencies have delivered their post-season best tracks; until then
its storms are `PROVISIONAL` or `US-PROVISIONAL` operational tracks, which the
agencies revise. On 2026-09-17 every 2023 and 2024 storm was `main`, most 2025
storms outside the Atlantic and northeast Pacific were still provisional, and
no 2026 storm was final. Category and peak wind come from the U.S. agency's
1-minute wind (`USA_SSHS` is -5 to -1 for depressions, subtropical, and
post-tropical stages); other agencies average over ten minutes, so their winds
are lower for the same storm.

A repeat pull uses the lockfile and checksummed cache. NCEI rebuilds this file
in place, under the same name, whenever an agency delivers tracks, so a later
`usdata pull` reports that the bytes changed upstream rather than fetching a
new revision: pass `--update noaa:ibtracs` to accept the current build, or keep the
lockfile and cached bytes to reproduce the analysis as it was. See
[NOAA access notes](https://docs.usdata.dev/providers/noaa-ibtracs/) for the
subsets, formats, and version selection.
