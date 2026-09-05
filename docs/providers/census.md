# Census Bureau

Provider id `census`. Homepage: https://www.census.gov/

## Access notes

No notes yet. Add how this agency publishes data, authentication requirements, quirks, and links to its own documentation as adapters get built.

## Datasets

<!-- datasets:start -->
Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

| Dataset | Status | Description | Protocol | Server-side subsetting |
|---|---|---|---|---|
| [`census:acs-5year`](#censusacs-5year) | planned | Population, housing, income, and demographic estimates for every geography down to block group, via the Census Data API. | http | spatial, temporal, variable |

### census:acs-5year

**American Community Survey 5-Year Estimates** · planned

Population, housing, income, and demographic estimates for every geography down to block group, via the Census Data API. Anonymous for light use; an API key lifts rate limits.

- Homepage: https://www.census.gov/data/developers/data-sets/acs-5year.html
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: population, demographics, housing, income, acs, census
- Adapter: none yet
<!-- datasets:end -->
