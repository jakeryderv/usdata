# Which earthquakes did Oklahoma record on the days of the May 2024 tornado outbreak?

Available since v0.19.0. The [manifest](dataset.yaml) asks the USGS earthquake
catalog for every event of magnitude 1.0 or more inside Oklahoma's bounding
box on 6 and 7 May 2024, the two days the severe-weather examples study. The
catalog answers with one CSV of fixed columns, one row per event, and the
manifest pins it. Oklahoma's induced seismicity means the answer is not zero.

In an activated Python 3.11+ virtual environment, install the published package
and save the [manifest](dataset.yaml) as `dataset.yaml` in a working directory.
Run the commands from that directory:

```sh
python -m pip install "usdata[pandas]"
usdata pull dataset.yaml
usdata verify dataset.yaml
```

Open the CSV with the same generic reader the station datasets use. Run this
with `python` in the same directory and environment:

```python
from pathlib import Path

from usdata import pull, verify

manifest = Path("dataset.yaml")
result = pull(manifest)
events = result.one("quakes").open(parse_dates=["time", "updated"])
print(len(events), "events;", int(events.status.eq("reviewed").sum()), "reviewed")
print(events.sort_values("mag", ascending=False)[["time", "place", "mag", "depth"]].head())
assert verify(manifest) == []
```

For a [source installation](https://docs.usdata.dev/install/#source-installation), run from
`examples/datasets/usgs-earthquakes/` and use `uv run usdata` and `uv run python`.

`mag` is on the scale `magType` names, mostly `ml` for these small local
events, `depth` is kilometers below sea level, and `time` and `updated` are
UTC. The location is the state's bounding box, so a few events just over the
border count too; filter on `place` or coordinates for a tighter answer. A
manifest that selects no event at all fails unless its source sets
`allow_empty: true`, which is the honest outcome for a quiet window.

The catalog revises events after networks review them, so `updated` can move
and a later pull can report drift; `pull --update` accepts the revised rows.
Keep the manifest, lockfile, and cached bytes together. Query details are in
the [earthquake catalog guide](https://docs.usdata.dev/providers/usgs-earthquakes/).

## What was awkward

- The service returns an empty CSV with only a header for a window with no
  events, but `usdata` never sees it: the count comes back as 0 and the source
  resolves to no assets, so the manifest fails with `EmptySource` unless
  `allow_empty` is set. That is correct and documented, but the first run of a
  quiet window reads like a broken query rather than an empty answer.
