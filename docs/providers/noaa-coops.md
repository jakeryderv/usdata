# CO-OPS observed water levels

Available since v0.10.0 as `noaa:coops-water-levels`. The initial adapter
fetches six-minute observed water levels for one explicit station. NOAA returns
preliminary or verified observations according to availability. Predictions,
currents, station discovery, and automatic request chunking are not included.

Require a seven-digit string `station`, an explicit uppercase `datum`, and both
timestamps. `units` is `metric` (default, meters) or `english` (feet). Supported
datum codes follow the [Data API documentation](https://api.tidesandcurrents.noaa.gov/api/dev/):
CRD, IGLD, LWD, MHHW, MHW, MTL, MSL, MLW, MLLW, NAVD, and STND. Availability of a
datum depends on the station; the service rejects unsupported combinations.
Unknown parameters, geographic/text selectors, and `variables` are rejected.

Offsets are normalized to UTC and the API request fixes `time_zone=gmt`. Bounds
are inclusive, must have zero seconds/microseconds, and span at most 28 days,
conservatively within NOAA's one-month limit. A date alone as the end means 23:59 on that day.
The adapter constructs one stable CSV request; it checks availability on fetch.

```sh
uv run usdata fetch noaa:coops-water-levels \
  --start 2024-05-06T00:00Z --end 2024-05-06T00:12Z \
  -p station=8518750 -p datum=MLLW -p units=metric
```

The raw CSV retains original header spacing, observations, and quality flags.
Use the ordinary CSV reader and rename columns locally if desired; station,
datum, units, and timezone remain explicit in the provenance source URL. The
[small manifest example](https://usdata.dev/datasets/noaa/coops-water-levels/) shows this.
Quality `p` and `v` mean preliminary and verified; preserve the quality field
alongside the flags because their interpretation changes. See the
[response definitions](https://api.tidesandcurrents.noaa.gov/api/prod/responseHelp.html).


See the [service research notes](noaa-services.md#co-ops-observed-water-levels) for dated upstream probes.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Resolution, updates, and the longest window: the [Data API
  documentation](https://api.tidesandcurrents.noaa.gov/api/prod/), which describes
  six-minute water levels, monthly verification of the past month, and a one-month
  retrieval limit; the adapter's `MAX_INTERVAL` in `usdata.providers.noaa.coops` sets
  the declared 28 days inside it.
- Variables: the CSV header this adapter requests and the [response
  definitions](https://api.tidesandcurrents.noaa.gov/api/prod/responseHelp.html).
- Terms: the [CO-OPS disclaimer](https://tidesandcurrents.noaa.gov/disclaimers.html),
  which asks that NOS be acknowledged as the source.
- Citation: CO-OPS publishes no citation form, so the entry uses the agency, product,
  and access form.
- Latency is empty: the API documentation states no lag between observation and
  availability.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/coops-water-levels.md#catalog-reference).
