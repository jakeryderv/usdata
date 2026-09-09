# CO-OPS observed water levels

**Unreleased:** use the [source installation](../../README.md#source-installation) before running these examples.

Available from source for v0.10 as `noaa:coops-water-levels`. The initial adapter
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
conservatively within NOAA's one-month limit. Date-only bounds remain midnight.
The adapter constructs one stable CSV request; it checks availability on fetch.

```sh
uv run usdata fetch noaa:coops-water-levels \
  --start 2024-05-06T00:00Z --end 2024-05-06T00:12Z \
  -p station=8518750 -p datum=MLLW -p units=metric
```

The raw CSV retains original header spacing, observations, and quality flags.
Use the ordinary CSV reader and rename columns locally if desired; station,
datum, units, and timezone remain explicit in the provenance source URL. The
[small manifest example](../../examples/coastal-water-levels/README.md) shows this.
Quality `p` and `v` mean preliminary and verified; preserve the quality field
alongside the flags because their interpretation changes. See the
[response definitions](https://api.tidesandcurrents.noaa.gov/api/prod/responseHelp.html).


See the [service research notes](noaa-services.md#co-ops-observed-water-levels) for dated upstream probes.

[All NOAA datasets](noaa.md).
