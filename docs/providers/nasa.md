# NASA

Provider id `nasa`. Homepage: https://www.earthdata.nasa.gov/

## Access notes

No notes yet. Add how this agency publishes data, authentication requirements, quirks, and links to its own documentation as adapters get built.

## Datasets

<!-- datasets:start -->
Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

| Dataset | Domain | Status | Version | Description | Protocol |
|---|---|---|---|---|---|
| [`nasa:gpm-imerg`](#nasagpm-imerg) | Weather satellites | planned | target 0.4 | Global half-hourly and daily merged satellite precipitation estimates. | http |

### nasa:gpm-imerg

**GPM IMERG Precipitation** · planned · target 0.4

Global half-hourly and daily merged satellite precipitation estimates. Discovered through NASA CMR and downloaded from GES DISC. Requires a free Earthdata Login; the first credentialed dataset.

- Domain: Weather satellites
- Server-side subsetting: temporal
- Homepage: https://gpm.nasa.gov/data/imerg
- License: NASA open data
- Extent: not stated
- Keywords: precipitation, rainfall, satellite, gpm, imerg, climate
- Adapter: none yet
<!-- datasets:end -->
