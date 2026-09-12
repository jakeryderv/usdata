# 0019: Climate normals as one dataset with a period parameter and placeholder-year windows

Status: accepted. Date: 2026-09-11.

## Context

NCEI serves 1991-2020 normals as separate Access Data Service datasets for
daily, monthly, annual/seasonal, and hourly values. Normals are 30-year
averages, not observations: monthly files label rows `MM`, daily files `MM-DD`,
and annual files have no date. The daily dataset still requires `startDate`
and `endDate`, ignores the year in them, and returns nothing for a window that
crosses the new year. Every other NCEI adapter requires both dates and selects
observation intervals, which does not describe normals.

## Decision

Register one dataset, `noaa:climate-normals`, and choose the upstream dataset
with a `period` parameter (`monthly` by default, `daily`, `annualseasonal`).
Hourly normals are not included. Dates are optional. For daily and monthly
normals a `start`/`end` pair selects a month-day window; usdata sends the
placeholder year 2020 so February 29 is valid, converts offset datetimes to UTC
first like the sibling adapters, and rejects windows that cross the new year
rather than returning an empty file. Without dates the whole year is requested
explicitly so equivalent queries share URLs and asset ids. Annual/seasonal
normals reject dates because the source cannot subset them.

Assets carry the 1991-2020 normals period as their time bounds; the calendar
window lives in the URL and asset id. Station discovery searches the selected
period's dataset over the normals period. The GHCN adapter's search loop gained
a dataset argument so the period can vary per query without duplicating
pagination. Units default to metric for consistency with the other NCEI
adapters even though the service default is standard.

## Consequences

Users write one manifest source per period rather than one dataset id per
period, and the catalog stays at one entry. A cross-year window such as
December to January needs two sources. An asset's time bounds describe the
averaging period, so time-based selection among normals assets is not
meaningful. Adding 2006-2020 or 1981-2010 normals, or hourly normals, would be
a further parameter or dataset rather than a change to this shape.
