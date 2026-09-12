# NEXRAD radar scans

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:nexrad-level2` · **Released** · Included since usdata 0.2.

NEXRAD Level II Radar.

## At a glance

- Files: NEXRAD Level II
- Selection: Whole radar scans by site and inclusive UTC scan-start time
- Required inputs: Both timestamps; radar IDs or a geographic query
- Open locally: `usdata[radar]` · [Reader guide](../../../reference/readers.md)
- Examples: [radar reflectivity](https://usdata.dev/examples/radar-reflectivity/), [event context](https://usdata.dev/examples/event-context/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `nearest` | Take the N radars nearest the query centre instead of naming sites. |
| `site` | One radar ICAO id, for example KTLX. |
| `sites` | Several radar ICAO ids, comma-separated or a list. |

## Usage and limitations

[Usage guide](../../../providers/noaa-nexrad.md).

## Catalog reference

- Availability: since 0.2
- Domain: Weather radar
- Geographic bounds (WGS84): west -180°, south 15°, east -60°, north 72°
- Catalog date range: 1991-06-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://registry.opendata.aws/noaa-nexrad/)
- License: US Government Work (public domain)
- Transport: `s3`
- Adapter: `usdata.providers.noaa.nexrad:NexradLevel2`

[All NOAA datasets](../noaa.md).
