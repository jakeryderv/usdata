# 0003: Raw CSV and absolute offsets for USGS daily values

Status: accepted. Date: 2026-09-05.

## Context

The first non-NOAA adapter needs anonymous access and reproducible assets.
Live probes confirmed that the modern Water Data OGC API serves daily values
by site or bbox, date range, parameter code, and statistic. It is the supported
modernized interface described in the [USGS migration guide](https://api.waterdata.usgs.gov/docs/ogcapi/migration/).
The [legacy WaterServices homepage](https://waterservices.usgs.gov/) announces
decommissioning in early 2027. New access therefore targets the modern API.

GeoJSON responses contain a per-request `timeStamp`. Pinning the entire
response would make restoration fail even when the observations are unchanged.
The service also offers raw CSV containing coordinates, units, quality flags,
and observation modification timestamps without that response timestamp.

Live pagination tests found two constraints: `sortby` requests fail after
page one, and a terminal cursor page can return an offset-based next link
that repeats a prior observation. Explicit offsets work with the service's
default ordering.

## Decision

Use the modern `/ogcapi/v0/collections/daily/items` endpoint. Discover pages
with JSON, and download the corresponding raw CSV representation for each
asset. Advance absolute offsets by the number of observations returned,
keeping the original filters and omitting `sortby`. Stop on an empty page or
when the service reports no next page.

Keep this dataset-specific logic in `WaterDaily`. No changes to `Query` or
`Provider` are needed. Use the existing HTTP transport and core provenance,
cache, and lockfile code.

## Consequences

The library records source CSV bytes without transforming the data. Small
live tests cover multiple pages, duplicate-free results, and restoration of
a missing cached file. A changed upstream observation or page membership
still produces a checksum mismatch: these requests do not expose immutable
historical versions. Large offset scans may be slower than cursor scans;
revisit the strategy when upstream pagination behavior changes.
