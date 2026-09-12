# Hourly airport observations

Available from source for the unreleased v0.14.0. The [manifest](dataset.yaml)
requests three days of Local Climatological Data at Oklahoma City's Will Rogers
World Airport through `noaa:lcd`: hourly temperature and precipitation together
with the daily maximum, minimum, and precipitation summary. Every row is one
report; `REPORT_TYPE` separates the hourly METAR reports (`FM-15`) from the
daily summary (`SOD`) that NCEI derives from them.

In an activated Python 3.11+ virtual environment, install the published package
and save the [manifest](dataset.yaml) as `dataset.yaml` in a working directory.
Run the commands from that directory:

```sh
python -m pip install "usdata[pandas]"
usdata pull dataset.yaml
usdata verify dataset.yaml
```

Check that the hourly reports reproduce each day's summary. Run this with
`python` in the same directory and environment:

```python
from pathlib import Path

import pandas as pd
from usdata import pull, verify

manifest = Path("dataset.yaml")
(item,) = pull(manifest).fetched
frame = item.open(parse_dates=["DATE"])
kind = frame["REPORT_TYPE"].str.strip()
day = frame["DATE"].dt.date
temperature = pd.to_numeric(frame["HourlyDryBulbTemperature"], errors="coerce")
hourly = temperature[kind == "FM-15"].groupby(day).agg(["max", "min", "count"])
summary = frame[kind == "SOD"].set_index(day[kind == "SOD"])
print(hourly.join(summary[["DailyMaximumDryBulbTemperature", "DailyMinimumDryBulbTemperature"]]))
assert verify(manifest) == []
```

For a [source installation](https://docs.usdata.dev/project/#source-installation), run from
`examples/hourly-observations/` and use `uv run usdata` and `uv run python`.

The daily extremes can exceed the hourly ones because the summary also uses
special reports and the station's continuous sensor, not only the top-of-hour
readings. Timestamps are the station's local standard time without an offset,
so a `DATE` value is not a UTC instant. Values may carry quality suffixes and
precipitation may be `T` for trace, which is why the snippet coerces the
temperature column. See [NOAA access notes](https://docs.usdata.dev/providers/noaa-lcd/)
for station ids, report types, and units.
