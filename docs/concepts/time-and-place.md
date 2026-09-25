# Time and place

Two kinds of argument select data: a time window and a place. Both are
normalized before an adapter sees them, and both have rules that are easy to
get wrong the first time.

## Time windows

--8<-- "_snippets/utc-window.md"

What a window selects depends on the dataset. A station query returns the
observations inside it. Whole-file archives such as Storm Events return every
annual file the window touches. Radar, satellite, and MRMS queries select files
whose start stamps fall inside the window, never files that merely overlap it.
Model output selects runs whose initialization time falls inside the window,
so a window given with times must reach the cycle hour, while a bare date
covers every hour of its day. Each dataset's guide states its rule and its
maximum window, and a window's length is measured between its instants: two
bare dates a day apart span two whole days, not one.

Some sources report local time in their rows even though the query was UTC.
Storm Events carries a `CZ_TIMEZONE` column for exactly this reason; convert
before joining to anything stamped in UTC.

## Choosing one file by time

Radar volumes, satellite scenes, and MRMS grids arrive every few minutes, and
an analysis often needs the one nearest a report. `select_by_time` chooses
among assets you have already listed, with an explicit policy: a
timezone-aware target, a tolerance measured from each asset's start, and a
direction, either `nearest` or `at_or_before`. The closest eligible start wins;
ties break by asset id. It performs no listing, download, or decoding, and it
raises rather than skipping an asset with a missing start time.

`at_or_before` means the file **started** at or before the target, not that
its acquisition had finished or that it was available by then. A scan can
start earlier and contain later observations. Publication delay, pixel and ray
timing, and any forecast-time availability cutoff are separate checks, as are
spatial alignment, parallax, and quality control. The helper compares assets
from different datasets if you ask it to; whether they are meaningful
alternatives is your call.

Save the returned selection's `model_dump_json()` beside your analysis. It
records the choice and the policy, not source provenance; keep the candidate
list if you need to audit alternatives. Arguments and result fields are in the
[selection reference](../reference/selection.md).

## Places

A `location` is a state, county, or county equivalent, given by name, postal
code, or quoted FIPS code, looked up in a bundled offline table from the
Census Bureau's 2025 cartographic boundary files. The result is a
longitude-latitude rectangle enclosing a generalized boundary, not the
boundary itself. It can include neighbouring counties, ocean, or anything
else inside the box, and providers apply their own selection rules to it:
NEXRAD falls back to the nearest radar when none lies inside. For exact
selection, name stations or sites.

The query also keeps the place itself, with its FIPS code, beside the
rectangle. Most sources never look at it. A source whose records are keyed by
state and county rather than by coordinates reads the place and selects exactly
that state or county, and refuses a bare `bbox` or `lat`/`lon`, which names no
place; its registry entry declares `place_subset`. So a location means a
rectangle to a grid, a way to choose stations to GHCN, and an exact county to a
place-keyed source ([ADR 0034](../adr/0034-query-keeps-the-resolved-place.md)).

The rectangle cannot wrap across the antimeridian. Alaska and Aleutians West,
whose westernmost islands lie beyond 180 degrees, therefore resolve to their
western-hemisphere part and omit the Near Islands and part of the Rat Islands
([places reference](../reference/places.md#antimeridian)); for those islands
pass a bbox or explicit sites, and split a wrapped region into two boxes yourself.
Arbitrary addresses are not geocoded. Accepted input forms and coverage counts
are in the [places reference](../reference/places.md).
