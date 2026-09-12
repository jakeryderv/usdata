# Radar scans

`noaa:nexrad-level2` downloads whole Level II scans over anonymous HTTPS from the
public archive. Provide both timestamps and a radar ID or geographic query.
Start with a dry run to inspect the number and size of files:

```sh
usdata fetch noaa:nexrad-level2 -p site=KTLX \
  --start 2024-05-06T20:00Z --end 2024-05-06T20:05Z --dry-run
```

UTC bounds include both endpoints. Timestamps without a timezone are treated
as UTC, including directly constructed SDK queries. Explicit offsets are converted
to UTC. A date-only end means midnight at the start of that day. Remove
`--dry-run` to download. There is no server-side variable subsetting; each file
contains the available scan moments.

`site` and `sites` are mutually exclusive and accept non-empty strings or lists.
IDs are case-insensitive. With a geographic query, `nearest` selects a positive
number of nearby radars and cannot be combined with explicit IDs. Selection
falls back to the nearest radar when none lies inside the bounding rectangle.

The bundled station list excludes test/research radars from default selection.
See [archive and station metadata notes](noaa-services.md#access-notes).
The optional `usdata[radar]` reader opens local scans with xradar; an explicit
zero-based `sweep` chooses a sweep. See [reader limits](../reference/readers.md),
[temporal selection](../reference/selection.md), and the
[executed radar example](https://usdata.dev/examples/radar-reflectivity/).

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/nexrad-level2.md#catalog-reference).
