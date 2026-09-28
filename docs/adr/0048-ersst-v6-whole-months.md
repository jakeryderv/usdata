# 0048: ERSST is version 6, selected by whole calendar months

Status: accepted. Date: 2026-09-28.

## Context

The El Niño snowfall study ([issue 390](https://github.com/jakeryderv/usdata/issues/390))
needs a sea surface temperature record long enough to classify every winter
since 1950 and to compute the Niño 3.4 index. `noaa:ersst` was a planned entry
for ERSST v5. Probing on 2026-09-28 found three ERSST directories at NCEI:

- `data/sea-surface-temperature-extended-reconstructed/v6/access/`: version 6,
  released in December 2025 and the one NCEI's product page describes. 185001
  to 202608, NetCDF4 throughout.
- `data/sea-surface-temperature-extended-reconstructed/v5/netcdf/`: version 5,
  linked from the same page, and frozen at 202602 since 2026-03-03.
- `pub/data/cmb/ersst/v5/netcdf/`: version 5, still updated, but linked from
  nowhere on the product page. Every file from 2008 onward is rewritten each
  month, and files before 2008 are classic NetCDF3 on a 360-day calendar.

CPC computes its ENSO indices from v6: the traditional Oceanic Niño Index,
and since 1 February 2026 the Relative Oceanic Niño Index (RONI), which
NOAA uses officially (NWS Public Information Statement 26-05). Only legacy
index files remain on v5.

## Decision

`noaa:ersst` reads version 6 from its official directory, and only version 6.
The registry says what an agency publishes as current, and v6 is that. It is
also the simpler source: one format and one calendar across 1850 to the
present, an anomaly field on the 1991-2020 base, and files that are not
rewritten every month, and it is what CPC's own indices are computed from.
The official index itself, RONI, subtracts a tropical mean and is rescaled,
so it is left to a pinned CPC table rather than rebuilt from these files.

An asset is one whole monthly file, `ersst.v6.YYYYMM.nc`. A window selects
every calendar month it touches, in UTC, and the asset's time is that whole
month, even though the file stamps its `time` coordinate at mid-month. There is
no subsetting and there are no parameters. A window that reaches a month the
directory does not list is refused, naming the newest month, rather than
returning the months that exist. This is the rule Storm Events follows for
years ([ADR 0010](0010-storm-events-annual-archives.md)). A window starting
before January 1850 is refused the same way.

The newest month is preliminary. Each monthly update writes the month just
ended and rewrites the month before it; the listing shows that pattern from
February 2026 onward. A lockfile pinning the newest month will report it as
changed once, which `verify --listing` and a restore surface as they would for
any revised file. The adapter does not mark the newest file specially. The
listing cannot say whether a month is final, only whether it is newest, and
that changes without the file changing.

## Alternatives

- **v5 from `pub/data/cmb`**, the only v5 directory still updated. It would need a
  NetCDF3 reader and cftime for the 360-day calendar (this was built and
  closed unmerged as #391). It would read a directory NCEI does not document,
  and every 2008+ pin would drift every month.
- **A `version` parameter serving both.** It would carry both costs for a
  comparison the study can make against CPC's published index instead.
- **One asset per window.** The files are 168 KB each, so bundling them would
  save nothing, and it would lose the per-month pin that shows which month was
  revised.

## Consequences

A 1950-2026 series is about 920 downloads of 168 KB, roughly 150 MB, fetched
one after another. The walkthrough and the study pin their months, so later
runs restore from the cache or the mirror. If NCEI publishes v6 under another
path, or issues a v7, the adapter changes and the change is recorded here.
