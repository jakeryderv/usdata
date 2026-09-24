# NEXRAD derived radar products

<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

`noaa:nexrad-level3` · **Released** · Included since usdata 0.15.

NEXRAD Level III Products.

## At a glance

- Files: NEXRAD Level III (no reader)
- Selection: Whole product files by site, product code, and inclusive UTC scan time since 2020-03-30
- Required inputs: Both timestamps; product codes; radar IDs or a geographic query
- Open locally: Local files; no bundled reader for this format
- Examples: [Which derived radar products did KTLX publish around a tornado report?](https://usdata.dev/examples/radar-products/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `nearest` | Take the N radars nearest the query centre instead of naming sites. |
| `products` | Required Level III product codes, comma-separated or a list, for example N0B,NMD. |
| `site` | One radar ICAO id, for example KTLX. |
| `sites` | Several radar ICAO ids, comma-separated or a list. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `N?B` | — | Base reflectivity, super-resolution (since 2022-02-18) |
| `N?G` | — | Base velocity, super-resolution (since 2022-02-18) |
| `N?Q` | — | Base reflectivity, 256 levels (retired 2022-09-08) |
| `N?U` | — | Base velocity, 256 levels (retired 2022-09-08) |
| `N?S` | — | Storm-relative mean radial velocity |
| `N?C` | — | Correlation coefficient |
| `N?X` | — | Differential reflectivity |
| `N?K` | — | Specific differential phase |
| `N?H` | — | Hydrometeor classification |
| `NCR` | — | Composite reflectivity |
| `EET` | — | Enhanced echo tops |
| `DVL` | — | Digital vertically integrated liquid |
| `NMD` | — | Mesocyclone detection |
| `NST` | — | Storm tracking information |
| `NTV` | — | Tornado vortex signature (retired 2022-05-24) |
| `NVW` | — | VAD wind profile |
| `DHR` | — | Digital hybrid-scan reflectivity |
| `HHC` | — | Hybrid hydrometeor classification |
| `DAA` | — | Digital one-hour precipitation accumulation |
| `DTA` | — | Digital storm-total precipitation accumulation |
| `DSP` | — | Digital storm-total precipitation |
| `OHA` | — | One-hour precipitation accumulation |

## Usage and limitations

[Usage guide](../../../providers/noaa-nexrad-level3.md).

## Catalog reference

- Availability: since 0.15
- Domain: Weather radar
- Temporal resolution: One file per product per volume scan; roughly 120 to 390 per product per day
- Updates: Files appear as the Unidata feed captures them, and coverage has gaps
- Longest query window: 31 days
- Terms of use: <https://www.noaa.gov/information-technology/open-data-dissemination>
- Citation: NEXRAD on AWS was accessed on [date] from https://registry.opendata.aws/noaa-nexrad
- Geographic bounds (WGS84): west -180°, south 15°, east -60°, north 72°
- Catalog date range: 2020-03-30 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://registry.opendata.aws/noaa-nexrad/)
- License: US Government Work (public domain)
- Transport: `s3`
- Adapter: `usdata.providers.noaa.nexrad_level3:NexradLevel3`

[All NOAA datasets](../noaa.md).
