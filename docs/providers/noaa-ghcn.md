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
The CSV has no units row; request provenance retains the unit system. NOAA can
revise observations, so preserve cached bytes alongside manifests and lockfiles.
See the [first-use walkthrough](../index.md) and
[weather/streamflow example](https://usdata.dev/examples/weather-and-streamflow/).

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/ghcn-daily.md#catalog-reference).
