# 0037: Hourly normals select calendar days and retain local-standard-time labels

Status: accepted. Date: 2026-09-21. Extends
[ADR 0019](0019-climate-normals-periods.md).

## Context

Hourly normals complete a bounded comparison with the existing LCD adapter:
one airport's observed temperatures beside its 1991–2020 hourly means. NCEI's
anonymous service uses the same station discovery and CSV endpoint as the
other normals periods. Live probes found that a date-only request returns all
24 hours, ignores the year, and converts `HLY-TEMP-NORMAL` from Fahrenheit to
Celsius correctly. A February 28–March 1 window returns 48 rows: the hourly
product has no February 29 values.

## Decision

Add `hourly` to the existing `period` parameter and retain the month-day
window contract. Query bounds select whole days, with UTC normalization before
extracting the month and day, exactly as for the other calendar periods. The
placeholder year remains 2020. Asset time bounds still describe the 1991–2020
averaging period. No request URL or asset id for an existing period changes.

Preserve the source's `MM-DDTHH:MM:SS` labels in local standard time and its
missing days. A station's normal is a calendar statistic, not a UTC instant.
The adapter neither assigns a year or timezone nor interpolates February 29.
The guide explains these rules, and the example makes its observation matching
explicit: routine LCD reports, nearest hour within ten minutes, with missing
and unmatched values counted. Arithmetic and plotting remain in the example.

## Alternatives and consequences

Sub-hour selection or a new hour parameter would add another window convention
without helping the one-day comparison. A separate dataset id would duplicate
the existing discovery and transport contract. Neither is needed here.

Users wanting a few hours fetch the containing days and filter locally. Queries
crossing the new year still need two sources. Hourly normals are not daily
normals, and a departure from an hourly mean is not a percentile or an estimate
of statistical rarity. The example states those limits.
