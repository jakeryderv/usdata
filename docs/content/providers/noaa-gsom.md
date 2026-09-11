# Global Summary of the Month

Available since v0.7 as `noaa:gsom`. The NCEI dataset is
`global-summary-of-the-month`, with anonymous CSV access and the same station
search/50-station chunking as GHCN-Daily. Geographic selection discovers station
IDs through the search endpoint; data requests use those explicit IDs. A data
request with only a bbox returns HTTP 400 (a station is required).
Use either `stations` or a location/bbox, not both. `units` is `metric` (default)
or `standard`; unknown parameters are rejected.

Both start and end dates are required. Every UTC calendar month touched by the
interval is returned in full: May 6–7 selects May; May 31–June 1 selects both
months. The adapter expands search and data bounds to those whole months, so
requests for the same months have identical asset URLs and IDs. Asset time bounds
cover full months; provenance pins the normalized source URL, while the manifest
retains the original query. CSV `DATE` is `YYYY-MM`.

Common variables include `PRCP` (monthly precipitation total) and `TAVG` (monthly
mean temperature). With metric output these are millimeters and degrees Celsius.
Variable availability depends on the station; unrecognized codes are rejected by
NCEI. The API CSV has no units row, so `open()` retains the URL's `units` setting
in provenance without adding a DataFrame units map. See the
[NCEI API documentation](https://www.ncei.noaa.gov/support/access-data-service-api-user-documentation)
and [monthly example](../../../examples/monthly-climate/README.md).


See the [service research notes](noaa-services.md#global-summary-of-the-month) for dated upstream probes.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/gsom.md#catalog-reference).
