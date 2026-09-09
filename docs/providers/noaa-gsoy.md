# Global Summary of the Year

**Unreleased:** use the [source installation](../../README.md#source-installation) before running these examples.

Available from source for v0.10 as `noaa:gsoy`. GSOY uses the
anonymous NCEI Access Data Service dataset `global-summary-of-the-year`, reusing
GHCN/GSOM station discovery, pagination, and 50-station CSV chunks. Require both
dates and either `stations` or a location/bbox, not both. `units` is `metric`
(default) or `standard`; unknown parameters and text queries are rejected.

Every UTC calendar year touched by the interval is selected in full: May 6–7
selects the whole year; December 31–January 1 selects both years. Search and data
requests use January 1 through December 31, giving equivalent year selections
identical URLs and asset IDs. Asset coverage labels complete years; the original
query remains in the manifest. A timezone offset can change the selected UTC year.

CSV `DATE` is a four-digit year. Use `item.open(dtype={"DATE": "string"})` to
preserve it as text with the existing pandas reader. Common variables are `PRCP`
(annual precipitation total, metric millimeters) and `TAVG` (annual mean
temperature, metric degrees Celsius). CSV contains no units row; provenance
retains the requested unit system. Variable availability depends on the station.

Some elements, including degree-day summaries, have hemisphere-dependent
accumulation seasons. Annual record labels do not mean every element represents
January–December observations. Consult the [GSOY field documentation](https://www.ncei.noaa.gov/pub/data/cdo/documentation/GSOY_documentation.pdf).
[Dataset metadata](https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc%3AC00947/html)
describes global GHCN-Daily-derived summaries and weekly updates. Revisions can
change CSV bytes; retain the cache as well as the manifest and lockfile.


See the [service research notes](noaa-services.md#global-summary-of-the-year) for dated upstream probes.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/gsoy.md#catalog-reference).
