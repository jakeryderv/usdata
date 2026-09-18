# How long before the 6 May 2024 Osage County tornado was a tornado warning issued?

Unreleased; available from source for v0.22. The [manifest](dataset.yaml) pins
two inputs: every NWS watch, warning, and advisory issued for Osage County,
Oklahoma on the evening of 6 May 2024, and the 2024 Storm Events archive, which
holds the report of the EF4 that struck the county that night. Setting the
warning's issuance beside the report's start time gives a lead time, and shows
what a county-level record can and cannot say about it.

In an activated Python 3.11+ virtual environment, install the package from
[source](https://docs.usdata.dev/install/#source-installation) and run from
`examples/warning-lead-time/`, using `uv run usdata` and `uv run python`:

```sh
usdata pull dataset.yaml
usdata verify dataset.yaml
```

```python
from pathlib import Path

from usdata import pull, verify

manifest = Path("dataset.yaml")
result = pull(manifest)
warnings = result.one("warnings").open(parse_dates=["iso_issued", "iso_expired"])
reports = result.one("reports").open()

tornado = reports[reports.EVENT_ID == "1184254"].iloc[0]
issued = warnings[(warnings.phenomena == "TO") & (warnings.significance == "W")]
in_effect = issued[
    (issued.iso_issued <= tornado.BEGIN_UTC) & (issued.iso_expired > tornado.BEGIN_UTC)
]
print(tornado.TOR_F_SCALE, "began", tornado.BEGIN_UTC)
print(issued[["eventid", "iso_issued", "iso_expired"]])
print("lead time:", tornado.BEGIN_UTC - in_effect.iso_issued.min())
assert verify(manifest) == []
```

On 2026-09-18 the county's evening held 14 events: seven Severe Thunderstorm
Warnings, four Tornado Warnings, a Tornado Watch, a Flash Flood Warning, and a
Flood Advisory, all from the Tulsa office. Storm Events starts the EF4 at
02:12 UTC on 7 May, which is 20:12 CST on the 6th, and ends it at 02:57.

| Tornado Warning | Issued (UTC) | Expired (UTC) | Relative to the 02:12 start |
|---|---|---|---|
| 44 | 01:34 | 02:00 | issued 38 minutes before, expired 12 minutes before |
| 45 | 01:56 | 02:45 | **issued 16 minutes before, in effect at the start** |
| 46 | 02:14 | 02:45 | issued 2 minutes after |
| 47 | 02:35 | 03:15 | issued 23 minutes after |

So the warning in effect when the tornado began had been out for **16 minutes**.
Warning 45 was issued before warning 44 expired, so some part of the county had
been under a tornado warning continuously for 38 minutes. The Tornado Watch
covering the county was issued at 19:05 UTC, seven hours earlier.

Which of those numbers is "the lead time" depends on something these rows cannot
say. A warning is a polygon, and a county is listed on it when the polygon
touches the county. Osage is the largest county in Oklahoma, so warning 44 may
have been for a different part of it, or a different storm, than the one that
produced this tornado, which the report tracks from 4 miles east-northeast of
Osage to 7 miles east of Okesa. The 16 minutes is safe to state as "a
tornado warning naming this county was in effect, issued 16 minutes earlier". It
is not a verification statistic, which needs the polygons:
[`noaa:nws-warnings`](https://docs.usdata.dev/generated/catalog/noaa/) is the
planned source for those.

The warnings source is selected by an exact county. `Osage County, OK` becomes
the NWS code `OKC113`: the state's postal code, `C`, and the county FIPS code. A
bounding box could not do that, and is refused. The window selects events by
when they were **issued**: to ask what was in effect at some moment, widen the
window backwards, as this one does from 18:00 UTC, and compare `iso_issued` and
`iso_expired` yourself, as the snippet does.

IEM processes the live NWS product stream and states no schedule for revising
its archive. The same request returned identical bytes when repeated, and if a
later pull does report drift, `pull --update` accepts the revised rows. Keep the manifest, lockfile, and cached bytes together. Query
details are in the
[warnings guide](https://docs.usdata.dev/providers/noaa-nws-vtec-events/).

## What was awkward

- The obvious question, "what was in effect at 02:12?", is not one the service
  can be asked. A window from 02:00 to 02:30 returns three events issued inside
  it, the 02:14 Tornado Warning among them, and misses warning 45, the one that
  was actually in effect, because it was issued at 01:56. The window has to reach back
  far enough to catch everything still running, and how far is a judgment: these
  warnings ran 26 to 49 minutes, and the watch nearly nine hours.
- The service's date-only parameters return nothing for spans that hold thirteen
  events, with no error. The adapter never sends them, but a first probe with
  `curl` and plain dates reads like an empty archive.
- Two timestamps that look interchangeable are not. `issued` and `expired` are
  the same instants as `iso_issued` and `iso_expired` in a second format, and
  only the ISO pair parses with a timezone.
- The county code needs the state's two-letter postal code, which the place a
  location resolves to did not carry until this source asked for it. FEMA had
  only ever needed the numeric FIPS code.
