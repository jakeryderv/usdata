# NEXRAD Level II Radar

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

<!-- dataset-usage -->
[Usage guide](../../../providers/noaa-nexrad.md).

## Catalog reference

**NEXRAD Level II Radar** · available · since 0.2

Raw volume scans from the WSR-88D weather radar network, archived in the public unidata-nexrad-level2 S3 bucket (NOAA Open Data Dissemination). One object per radar site per volume scan. No server-side subsetting; whole files are fetched. Select radars by site id, bbox, or nearest to a point.

- Domain: Weather radar
- Server-side subsetting: temporal
- Homepage: https://registry.opendata.aws/noaa-nexrad/
- License: US Government Work (public domain)
- Extent: -180, 15, -60, 72; 1991-06-01 to present
- Keywords: radar, weather, storms, tornado, precipitation, reflectivity, nexrad, wsr-88d
- Adapter: `usdata.providers.noaa.nexrad:NexradLevel2`
