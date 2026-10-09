# Radar scans

`noaa:nexrad-level2` downloads whole Level II scans over anonymous HTTPS from the
public archive. Provide both timestamps and a radar ID or geographic query.
Start with a dry run to inspect the number and size of files:

```sh
usdata fetch noaa:nexrad-level2 -p site=KTLX \
  --start 2024-05-06T20:00Z --end 2024-05-06T20:05Z --dry-run
```

A query spans at most 31 days; split longer intervals. Remove `--dry-run` to
download. There is no server-side variable subsetting; each file contains the
available scan moments.

--8<-- "_snippets/utc-window.md"

`site` and `sites` are mutually exclusive and accept non-empty strings or lists.
IDs are case-insensitive. With a geographic query, `nearest` selects a positive
number of nearby radars and cannot be combined with explicit IDs. Selection
falls back to the nearest radar when none lies inside the bounding rectangle.

The bundled station list excludes test/research radars from default selection.
See [archive and station metadata notes](noaa-services.md#access-notes).

## Coverage outside the declared extent

The catalog extent, 180°W to 27°W and 15°N to 72°N, holds every bundled radar
in the western hemisphere, from the Aleutians to Lajes in the Azores (`LPLA`).
Four radars lie across the antimeridian from it: Andersen AFB on Guam (`PGUA`),
Kunsan (`RKJK`) and Camp Humphreys (`RKSG`) in Korea, and Kadena on Okinawa
(`RODN`). A box cannot wrap across 180°, and one spanning every longitude would
match any search anywhere, so these four stay outside the extent. Registry
search by place or point does not list the radar datasets there; fetch them by
site id (`-p site=PGUA`), or with a geographic query, which falls back to the
nearest radar. A registry test keeps this list and the bundled table in agreement.
The optional `usdata[radar]` reader opens local scans with xradar; an explicit
zero-based `sweep` chooses a sweep. See [choosing sweeps](#choosing-sweeps),
[reader limits](../reference/readers.md),
[temporal selection](../reference/selection.md), and the
[executed radar example](https://usdata.dev/datasets/noaa/nexrad-level2/).

## Choosing sweeps

A sweep index is a position in the volume, not an elevation. Each low angle is
a split cut, scanned once for reflectivity and the dual-polarization moments
and once more for velocity, and SAILS rescans the lowest angle inside the
volume. `KTLX20240507_021123_V06`, the KTLX volume in progress when the
Barnsdall EF4 began, is VCP 212 with three SAILS cuts, 23 sweeps over seven
minutes:

```text
$ usdata inspect noaa:nexrad-level2/KTLX20240507_021123_V06
  vcp:       212
  sweeps:
    #   cut  angle  moments                                 start     end       rays  notes
    0   1    0.48   DBZH ZDR PHIDP RHOHV CCORH              02:11:23  02:11:39  720
    1   2    0.48   DBZH VRADH WRADH                        02:11:40  02:12:04  720
    2   3    0.88   DBZH ZDR PHIDP RHOHV CCORH              02:12:05  02:12:21  720
    3   4    0.88   DBZH VRADH WRADH                        02:12:23  02:12:46  720
    4   5    0.48   DBZH ZDR PHIDP RHOHV CCORH              02:12:47  02:13:04  717   SAILS
    5   6    0.48   DBZH VRADH WRADH                        02:13:05  02:13:29  720   SAILS
    ...
    8   9    1.80   DBZH VRADH WRADH ZDR PHIDP RHOHV CCORH  02:14:11  02:14:24  360
    ...
    16  17   0.48   DBZH ZDR PHIDP RHOHV CCORH              02:16:18  02:16:34  720   SAILS
    17  18   0.48   DBZH VRADH WRADH                        02:16:35  02:16:59  720   SAILS
    ...
    22  23   19.51  DBZH VRADH WRADH ZDR PHIDP RHOHV CCORH  02:17:55  02:18:07  360
```

The 0.5° angle is eight sweeps, four of reflectivity and four of velocity, and
a VCP without SAILS puts different angles at those indices. In this volume
velocity (`VRADH`) and spectrum width (`WRADH`) arrive only on the Doppler half
of each split cut, at 1.32° and below, and on every sweep from 1.80° up.

To select the same scan in every volume, choose by angle, moment, and time
rather than by index. `readers.nexrad_sweeps` reads that table from the
volume's metadata without decoding any moment, and `item.inspect().nexrad`
returns it with the VCP number:

```python
from usdata.readers import nexrad_sweeps

sweeps = nexrad_sweeps(item.path)
lowest = min(sweep.fixed_angle for sweep in sweeps)
first_velocity = next(s for s in sweeps if s.fixed_angle == lowest and "VRADH" in s.moments)
radar = item.open_nexrad(sweep=first_velocity.index)
```

Whether to take the first lowest-angle scan of each volume or every SAILS
rescan is a choice the analysis makes: here the rescans add three more
low-level velocity scans, starting 85 to 112 seconds apart, all later than the
time in the file name. Each sweep's `start` and `end` say when.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Temporal resolution: the [NCEI NEXRAD product
  page](https://www.ncei.noaa.gov/products/radar/next-generation-weather-radar), which
  says a Level II file typically holds four, five, six, or ten minutes of base data
  depending on the volume coverage pattern.
- Updates, citation, and terms: the [NODD registry
  entry](https://registry.opendata.aws/noaa-nexrad/) ("New Level II data is added as
  soon as it is available") and the [NOAA Open Data
  Dissemination](https://www.noaa.gov/information-technology/open-data-dissemination)
  statement it quotes.
- Variables: the moments the `radar` reader returns across every sweep of
  `KTLX20240507_021123_V06`, decoded on 2026-10-08, with the units it states;
  velocity and spectrum width in m/s, which the reader writes as "meters per
  seconds".
- Longest query window: `MAX_WINDOW` in `usdata.providers.noaa.nexrad`.
- Spatial resolution and latency are empty: the NCEI page refers gate and azimuth
  spacing to Federal Meteorological Handbook No. 11, and neither NCEI nor NODD publishes
  a latency figure for the archive.

[All NOAA datasets](noaa.md).

--8<-- "generated/catalog/noaa/nexrad-level2.md"
