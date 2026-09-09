# Census Bureau dataset catalog

[Provider access notes](../../providers/census.md). Status describes this source checkout; see version labels for release support.

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

| Dataset | Domain | Status | Version | Description | Protocol |
|---|---|---|---|---|---|
| [`census:acs-5year`](#censusacs-5year) | Demographics | planned | target later | Population, housing, income, and demographic estimates for every geography down to block group, via the Census Data API. | http |

### census:acs-5year

**American Community Survey 5-Year Estimates** · planned · target later

Population, housing, income, and demographic estimates for every geography down to block group, via the Census Data API. Anonymous for light use; an API key lifts rate limits.

- Domain: Demographics
- Server-side subsetting: spatial, temporal, variable
- Homepage: https://www.census.gov/data/developers/data-sets/acs-5year.html
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: population, demographics, housing, income, acs, census
- Adapter: none yet
