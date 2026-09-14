# One year of SPC tornado reports

Available since v0.15.0. The [manifest](dataset.yaml) requests the Storm
Prediction Center's 2024 tornado file through `noaa:spc-tornado-reports`: one
CSV of about 230 KB with one row per tornado, plus one extra row per state for
tornadoes that crossed a state line. Each row carries the touchdown date and
time, the EF rating, injuries and fatalities, start and end coordinates, and
the path length and width.

In an activated Python 3.11+ virtual environment, install the published package
and save the [manifest](dataset.yaml) as `dataset.yaml` in a working directory.
Run the commands from that directory:

```sh
python -m pip install "usdata[pandas]"
usdata pull dataset.yaml
usdata verify dataset.yaml
```

Count the year's tornadoes by rating and total the path length of the strongest
ones. Run this with `python` in the same directory and environment:

```python
from pathlib import Path

from usdata import pull, verify

manifest = Path("dataset.yaml")
(item,) = pull(manifest).fetched
frame = item.open(dtype={"stf": "string", "f1": "string"}, parse_dates=["date"])
tracks = frame[frame["sg"] == 1]
print(tracks["mag"].value_counts().sort_index().rename("tornadoes"))
strong = tracks[tracks["mag"] >= 3]
print(f"{len(strong)} tornadoes rated EF3 or higher, {strong['len'].sum():.0f} path miles")
print(tracks.nlargest(3, "len")[["date", "time", "st", "mag", "len", "wid", "fat"]])
assert verify(manifest) == []
```

For a [source installation](https://docs.usdata.dev/install/#source-installation), run from
`examples/spc-tornadoes/` and use `uv run usdata` and `uv run python`.

Keeping only `sg == 1` counts each tornado once; the `sg == 2` rows repeat a
multi-state tornado for each state it entered. A rating of `-9` means the
tornado was never rated, so it is a category in the counts rather than a
missing value. Times are Central Standard Time on every row, not the local
zone of the tornado. Damage figures are unreliable and are left out above. The
same year in `noaa:storm-events` has more rows, because that database records
one row per county segment with a narrative. See the
[NOAA access notes](https://docs.usdata.dev/providers/noaa-spc-tornado/) for
the column definitions and the differences between the two databases.
