# NEXRAD derived radar products

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

`noaa:nexrad-level3` · **Released** · Included since usdata 0.15.

NEXRAD Level III Products.

## At a glance

- Files: NEXRAD Level III (no reader)
- Selection: Whole product files by site, product code, and inclusive UTC scan time since 2020-03-30
- Required inputs: Both timestamps; product codes; radar IDs or a geographic query
- Open locally: Local files; no bundled reader for this format
- Examples: [radar products](https://usdata.dev/examples/radar-products/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `nearest` | Take the N radars nearest the query centre instead of naming sites. |
| `products` | Required Level III product codes, comma-separated or a list, for example N0B,NMD. |
| `site` | One radar ICAO id, for example KTLX. |
| `sites` | Several radar ICAO ids, comma-separated or a list. |

## Usage and limitations

[Usage guide](../../../providers/noaa-nexrad-level3.md).

## Catalog reference

- Availability: since 0.15
- Domain: Weather radar
- Geographic bounds (WGS84): west -180°, south 15°, east -60°, north 72°
- Catalog date range: 2020-03-30 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://registry.opendata.aws/noaa-nexrad/)
- License: US Government Work (public domain)
- Transport: `s3`
- Adapter: `usdata.providers.noaa.nexrad_level3:NexradLevel3`

[All NOAA datasets](../noaa.md).
