# 0004: ERDDAP CSV and coordinate-based subsets

Status: accepted. Date: 2026-09-05.

## Context

CoastWatch's [blended SST metadata](https://coastwatch.noaa.gov/erddap/info/noaacwBLENDEDsstDNDaily/index.html)
exposes a 0.05-degree global grid and an irregular daily time axis beginning
2019-07-22 at noon UTC. A query must select coordinates inside the requested
bounds without silently snapping to another day or a neighboring grid cell.

Live probes of the same tiny subset returned different NetCDF bytes because
ERDDAP adds request timestamps to its `history` attribute. Repeated CSV requests
returned identical bytes while retaining coordinates and a units row.

## Decision

Download raw griddap CSV, without response transformation. Support the four
advertised variables, defaulting to `analysed_sst`. Keep ERDDAP metadata, axis
parsing, and URL grammar in a transport module; keep dataset dimensions,
variables, and selection policy in the CoastWatch adapter.

Validate spatial metadata, calculate contained grid centers, and read the actual
time axis before selecting inclusive timestamps. Use coordinate values in asset
URLs rather than indices that could shift when historical coverage changes.
Sort/deduplicate variables for stable IDs. Allow a positive spatial stride and
cap requests at one million output grid rows. An empty intersection returns no
assets and participates in the existing manifest empty-source policy.

## Consequences

No scientific dependency is added. Consumers must handle ERDDAP's second CSV
header row containing units. NetCDF output and optional readers remain future
work. Time-axis discovery costs a small request on each resolution, while locked
restoration uses pinned URLs directly. Historical observations can still change;
checksums detect this but cannot recover old upstream bytes. Tiny live tests
exercise repeated downloads and locked restoration.
