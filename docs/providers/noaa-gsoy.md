# Global Summary of the Year

Available since v0.10.0 as `noaa:gsoy`. GSOY uses the
anonymous NCEI Access Data Service dataset `global-summary-of-the-year`, reusing
GHCN/GSOM station discovery, pagination, and 50-station CSV chunks. Require both
dates and either `stations` or a location/bbox, not both. `units` is `metric`
(default) or `standard`; unknown parameters and text queries are rejected.

Every UTC calendar year touched by the interval is selected in full: May 6–7
selects the whole year; December 31–January 1 selects both years. Search and data
requests use January 1 through December 31, giving equivalent year selections
identical URLs and asset IDs. Asset coverage labels complete years; the original
query remains in the manifest. A timezone offset can change the selected UTC year.

CSV `DATE` is a four-digit year. Use `item.open_csv(dtype={"DATE": "string"})` to
preserve it as text with the existing pandas reader. Common variables are `PRCP`
(annual precipitation total, metric millimeters) and `TAVG` (annual mean
temperature, metric degrees Celsius). CSV contains no units row; the frame's
`attrs["usdata"]["properties"]["units"]` records the requested unit system. Variable availability depends on the station.

Some elements, including degree-day summaries, have hemisphere-dependent
accumulation seasons. Annual record labels do not mean every element represents
January–December observations. Consult the [GSOY field documentation](https://www.ncei.noaa.gov/pub/data/cdo/documentation/GSOY_documentation.pdf).
[Dataset metadata](https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc%3AC00947/html)
describes global GHCN-Daily-derived summaries and weekly updates. Revisions can
change CSV bytes; retain the cache as well as the manifest and lockfile.


See the [service research notes](noaa-services.md#global-summary-of-the-year) for dated upstream probes.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Updates, citation, and terms: the [NCEI dataset
  record](https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C00947/html),
  which states weekly updates and the Lawrimore et al. (2016) citation with its DOI.
- Resolution and variables: the same record and the element codes this guide names, with
  the units the Access Data Service returns under `units=metric`. The element set is
  open and station-dependent.
- Latency is empty: the record states no lag between a year's end and its summary.

[All NOAA datasets](noaa.md).

--8<-- "generated/catalog/noaa/gsoy.md"
