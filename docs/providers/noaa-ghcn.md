# Daily station observations

`noaa:ghcn-daily` returns anonymous NCEI daily-summaries CSV. Provide both dates
and explicit `stations` or a geographic query. Stations can be a comma-separated
string or a list; explicit IDs take precedence over geographic discovery.

```sh
usdata fetch noaa:ghcn-daily -p stations=USW00013967 \
  --start 2024-05-06 --end 2024-05-07 --vars PRCP,TMAX
```

Dates are inclusive calendar dates; time of day is ignored. `units` is `metric`
(default) or `standard`. Variables use NCEI element codes, such as precipitation
`PRCP` and maximum temperature `TMAX`; availability depends on the station.
Unknown adapter options are rejected.

Geographic queries first discover station IDs using the NCEI search service,
then request CSV in groups of up to 50 stations. Search and data service outages
can occur independently. See [service diagnostics](noaa-services.md#access-notes).

Open the downloaded file with the [pandas reader](../reference/readers.md).
The CSV has no units row; request provenance retains the unit system.
See the [getting-started walkthrough](../getting-started.md) and
[weather/streamflow example](https://usdata.dev/examples/weather-and-streamflow/).

--8<-- "_snippets/upstream-revisions.md"

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Resolution, updates, latency, and citation: the [NCEI GHCNd product
  page](https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily),
  which states the station count, the weekend reconstruction, the 45-to-60-day
  replacement of real-time streams, and the Menne et al. (2012) citation.
- Terms: the [NCEI dataset
  record](https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C00861/html),
  which carries the access and use constraints.
- Variables: the element codes this guide names, with the units the Access Data Service
  returns under `units=metric`. The element set is open and station-dependent.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/ghcn-daily.md#catalog-reference).
