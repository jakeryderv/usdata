# CoastWatch SST

Available since v0.5. The verified dataset is
[`noaacwBLENDEDsstDNDaily`](https://coastwatch.noaa.gov/erddap/info/noaacwBLENDEDsstDNDaily/index.html),
a daily blended day/night SST analysis on `(time, latitude, longitude)`.
Latitude has 3,600 centers from -89.975 to 89.975; longitude has 7,200 from
-179.975 to 179.975, both spaced 0.05 degrees. The time axis starts at
2019-07-22T12:00:00Z and has gaps; the adapter reads actual available timestamps.
Its metadata describes data use as free and open under the GHRSST protocol.

| Variable | Meaning | Units |
|---|---|---|
| `analysed_sst` (default) | Sea surface temperature | degree_C |
| `analysis_error` | Estimated analysis error | degree_C |
| `sea_ice_fraction` | Sea ice fraction | 1 |
| `mask` | Source mask flags | Byte codes; consult source metadata |

Require a bbox/location and both timestamps. Bounds include only grid centers
and timestamps inside the requested interval; an interval with no matching
coordinates returns no assets. UTC bounds are inclusive. A date-only end means
midnight at the start of that date, before the noon analysis. `params.stride`
(or `-p stride=2`) subsamples both spatial axes with a positive integer. Reduce
the area/time window or increase stride when a query exceeds 1,000,000 rows.
Unknown parameters and variables fail explicitly.

The asset is raw CSV with coordinate columns, a header, and a second row of
units. This avoids the volatile per-request `history` timestamps observed in
NetCDF responses; see [ADR 0004](../adr/0004-erddap-csv-and-coordinate-subsets.md).
Upstream revisions still cause checksum mismatches during locked restoration.


See the [service research notes](noaa-services.md#coastwatch-sst) for dated upstream probes.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/coastwatch-sst.md#catalog-reference).
