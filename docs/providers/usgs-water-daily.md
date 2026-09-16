# Daily water observations

`usgs:water-daily` uses the [modern Water Data OGC API](https://api.waterdata.usgs.gov/docs/ogcapi/),
at `https://api.waterdata.usgs.gov/ogcapi/v0/collections/daily/items`.
The [legacy WaterServices homepage](https://waterservices.usgs.gov/) announces
decommissioning in early 2027 (checked 2026-09-05), so new access targets the
modern API.

- Select sites with `-p sites=07164500` or `USGS-07164500`; comma-separated IDs
  and SDK lists are supported. A location, bbox, or point can select sites
  geographically instead. When both site IDs and a bbox are provided, both apply.
- `--vars 00060` selects streamflow. Variables are five-digit parameter codes;
  quote codes in YAML to preserve leading zeros. Omitting variables requests
  all available parameters for the selected sites and dates.
- `-p statistic_id=00003` selects daily means (the default). Other five-digit
  statistic codes can select minima or maxima. Start and end are inclusive
  local calendar dates; times of day are ignored for daily values.
- A one-row JSON probe at each page offset resolves the query without
  downloading page contents; each asset downloads the corresponding raw CSV.
  CSV retains coordinates, units, approval status, qualifiers, and modification
  timestamps, while excluding the volatile GeoJSON response `timeStamp`.
- Live checks on 2026-09-05 found that `sortby` is rejected beyond the first
  page. Cursor links can also fall back to `offset=1` at the end, repeating a
  record. The adapter therefore uses absolute offsets advanced by the number
  of returned observations, retaining all original filters. Requests use
  10,000 rows per page; the integration test forces one row per page.
- Access was verified without credentials. [API keys](https://api.waterdata.usgs.gov/docs/ogcapi/keys/)
  raise rate limits but are not required for the supported small queries.
  API key configuration is not exposed by this adapter.
- The [service homepage](https://api.waterdata.usgs.gov/ogcapi/v0/?f=html)
  identifies its data as US Government work in the public domain.

Reproducibility pins the CSV bytes; the service does not offer immutable
versions through these requests.

--8<-- "_snippets/upstream-revisions.md"

Small probe used to verify the endpoint and filtering:

```sh
curl --get 'https://api.waterdata.usgs.gov/ogcapi/v0/collections/daily/items' \
  --data-urlencode 'f=csv' --data-urlencode 'monitoring_location_id=USGS-07164500' \
  --data-urlencode 'parameter_code=00060' --data-urlencode 'statistic_id=00003' \
  --data-urlencode 'time=2024-05-06/2024-05-07' --data-urlencode 'limit=1' \
  --data-urlencode 'offset=0'
```


## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Resolution and updates: the [OGC API
  documentation](https://api.waterdata.usgs.gov/docs/ogcapi/), which says daily data are
  automatically calculated from the continuous data of the same parameter code.
- Variables: the parameter codes this guide names, with the units the CSV carries. Any
  NWIS parameter code can appear, so the list is a sample.
- Terms: the [USGS copyrights and credits
  page](https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits),
  which places USGS-produced data in the public domain and asks for credit.
- Citation: USGS publishes no citation form for these records, so the entry uses the
  agency, product, and access form.
- Latency is empty: the API documentation states no lag between a day's end and its
  daily value.

[USGS access notes](usgs.md).

[Catalog reference](../generated/catalog/usgs/water-daily.md#catalog-reference).
