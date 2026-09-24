# How far above the daily PM2.5 standard did Canadian wildfire smoke push New York City's air in June 2023?

Available since v0.26.0. The [manifest](dataset.yaml) pins EPA's daily PM2.5
summaries from the regulatory monitors in a box around New York City for 1 to 15
June 2023, when smoke from wildfires in Quebec reached the city. It is the first
example that needs a key: `epa:aqs-daily` reads `USDATA_AQS_EMAIL` and
`USDATA_AQS_KEY` from the environment, and the
[AQS guide](https://docs.usdata.dev/providers/epa-aqs-daily/) says how to get
one. The manifest and its committed lockfile hold no key.

In an activated Python 3.11+ virtual environment, install the published package,
set the two variables, and save the [manifest](dataset.yaml) as `dataset.yaml`
in a working directory. Run the commands from that directory:

```sh
python -m pip install "usdata[pandas]"
usdata pull dataset.yaml
usdata verify dataset.yaml
```

For a [source installation](https://docs.usdata.dev/install/#source-installation), run from
`examples/wildfire-smoke/` and use `uv run usdata` and `uv run python`.

Without a key, the committed [lockfile](dataset.lock.json) can still be
restored: save it beside the manifest, set
`USDATA_MIRROR_URL=https://data.usdata.dev`, and `usdata pull` takes the pinned
file from the project mirror without asking EPA. It says it did so, and that
upstream was not checked for changes.

```python
from pathlib import Path

from usdata import pull, verify

manifest = Path("dataset.yaml")
pm25 = pull(manifest).one("pm25").open()

# One row per monitor and day: New York State only, the current daily standard,
# and smoke days counted rather than excluded.
daily = pm25[
    (pm25.state_code == "36")
    & (pm25.pollutant_standard == "PM25 24-hour 2024")
    & ~pm25.event_type.isin(["Events Excluded", "Concurred Events Excluded"])
]
assert not daily.duplicated(["county_code", "site_number", "poc", "date_local"]).any()
daily = daily.assign(
    monitor=daily.county_code + "-" + daily.site_number + "/" + daily.poc.astype(str)
)
by_day = daily.groupby(daily.date_local.dt.date).agg(
    monitors=("monitor", "nunique"),
    median=("arithmetic_mean", "median"),
    highest=("arithmetic_mean", "max"),
    above_standard=("arithmetic_mean", lambda values: int((values > 35).sum())),
)
print(by_day.round(1))
assert verify(manifest) == []
```

On 2026-09-23 the pinned file held 1,790 rows (1.6 MB). After the filters above,
13 monitors at 8 New York City sites remained, with no monitor reporting twice
on a day. The four continuous monitors report daily; the filter-based samplers
add readings on their own schedules, so the count varies from 4 to 13.

| Day | Monitors | Median (µg/m³) | Highest (µg/m³) | Above 35 µg/m³ |
|---|---:|---:|---:|---:|
| 5 June | 11 | 11.5 | 12.5 | 0 |
| 6 June | 5 | 85.6 | 101.0 | 5 |
| 7 June | 4 | 190.0 | 203.5 | 4 |
| 8 June | 9 | 61.0 | 106.9 | 9 |
| 9 June | 4 | 12.1 | 15.1 | 0 |
| 11 June | 13 | 24.2 | 35.2 | 1 |

Every New York monitor that reported on 6, 7, and 8 June was above the daily
standard of 35 µg/m³. The highest daily mean was 203.5 µg/m³ at Queens College
on 7 June, nearly six times the standard, with an AQI of 278 ("Very Unhealthy").
The rest of the fortnight stayed below it, apart from one monitor at 35.2
µg/m³ on 11 June. This is a statement about daily means at regulatory
monitors, not about exposure: a daily mean hides the afternoon peak, and a
handful of sites stands in for a city of eight million.

AQS is revised when agencies correct data, and each row carries
`date_of_last_change`. For the New York rows the latest was 17 July 2025, more
than a year after the 2023 data were certified, so a pin on this file can
drift. A later pull that reports it can accept the revision with
`pull --update`. Query details are in the
[AQS guide](https://docs.usdata.dev/providers/epa-aqs-daily/).

## What was awkward

- The box took in New Jersey. Fort Lee, Jersey City, Union City, Paterson, and
  Elizabeth sit inside any rectangle drawn around the five boroughs, and they
  were 9 of the 22 monitors. `state_code == "36"` keeps New York, which
  inside this box is exactly the city. Naming the five boroughs as five
  `location` sources would select each county exactly, at five slow requests
  instead of one.
- One monitor-day is up to nine rows: one for each of eight PM2.5 standards,
  plus the hourly series with no standard. Counting rows above 35 µg/m³ would
  count most monitors eight or nine times. Filtering to one standard is the
  whole fix, but nothing in the file says to do it.
- Exceptional events are not flagged by day. A monitor with any flagged event
  gets an `Events Included` copy of every row, so all fifteen days carry event
  rows, not only the smoke days. Here the New Jersey monitors also carried
  `Concurred Events Excluded` rows, which leave the smoke out. Keeping
  `No Events` and `Events Included` answers "what was measured"; the excluded
  rows answer "what counts toward the regulatory design value".
- The first live pull asked for nothing. httpx replaces a URL's whole query
  when it is given `params=`, so adding the key that way threw away the box and
  the dates. EPA's refusal, `variable is missing or the value is empty: param`,
  came back in the response header, and the adapter now reports it instead of
  a bare 400.
- It is slow. Requests took one to two minutes each when the service was
  probed, and EPA asks for a pause between them, which the adapter enforces.
