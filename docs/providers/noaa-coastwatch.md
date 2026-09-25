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
and timestamps inside the requested interval. A point (`--lat`/`--lon` with no
radius) or a box too small to hold a grid center selects the one cell at its
middle; a window with no analysis time returns no assets. UTC bounds are inclusive. A date alone as the
end runs through that day, so it includes the day's noon analysis. `params.stride`
(or `-p stride=2`) subsamples both spatial axes with a positive integer. Reduce
the area/time window or increase stride when a query exceeds 1,000,000 rows.
Unknown parameters and variables fail explicitly.

The asset is raw CSV with coordinate columns, a header, and a second row of
units. This avoids the volatile per-request `history` timestamps observed in
NetCDF responses; see [ADR 0004](https://github.com/jakeryderv/usdata/blob/main/docs/adr/0004-erddap-csv-and-coordinate-subsets.md).
--8<-- "_snippets/upstream-revisions.md"


See the [service research notes](noaa-services.md#coastwatch-sst) for dated upstream probes.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Resolution, updates, and terms: the [ERDDAP dataset
  metadata](https://coastwatch.noaa.gov/erddap/info/noaacwBLENDEDsstDNDaily/index.html),
  whose `spatial_resolution` is 0.05 degree, whose time axis averages one day, and whose
  `license` attribute states that the GHRSST protocol describes data use as free and
  open.
- Variables: the same metadata, as reproduced in the variable table above.
- Citation: no citation is published for the ERDDAP dataset, so the entry uses the
  agency, product, and access form, naming NOAA/NESDIS OSPO as the metadata's creator.
- Latency is empty: the metadata publishes no lag figure. Its `testOutOfDate` threshold
  is a staleness alarm for the ERDDAP server, not a stated latency.

[All NOAA datasets](noaa.md).

--8<-- "generated/catalog/noaa/coastwatch-sst.md"
