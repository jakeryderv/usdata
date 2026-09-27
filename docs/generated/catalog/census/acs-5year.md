<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

## Reference

`census:acs-5year` · **Source only** · Install from [source](../install.md#source-installation) to use this dataset. American Community Survey 5-Year Estimates.

### At a glance

- Files: JSON
- Selection: One vintage's estimates for up to fifty variables over a state, its counties, or one county
- Required inputs: A vintage; one to fifty variables; a state or county location
- Credentials: `USDATA_CENSUS_KEY` in the environment ([request a key](https://api.census.gov/data/key_signup.html))
- Open locally: `usdata[pandas]` · [Reader guide](../reference/readers.md)
- On usdata.dev: [Five-year population, housing, and income estimates by state or county](https://usdata.dev/datasets/census/acs-5year/), with a walkthrough

### Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `geography` | What each row is: state or county. Defaults to the kind of place the location names; county with a state location gives every county in it. |
| `vintage` | Required last year of the five-year period, such as 2023 for 2019-2023; the estimates are selected by vintage, not by a date window. |

### Variables

| Variable | Units | Meaning |
|---|---|---|
| `NAME` | — | Geographic area name, such as Osage County, Oklahoma |
| `B01003_001E` | — | Total population, estimate |
| `B01003_001M` | — | Total population, margin of error |
| `B25001_001E` | — | Housing units, estimate |
| `B25001_001M` | — | Housing units, margin of error |
| `B19013_001E` | US dollars of the vintage year | Median household income in the past 12 months, inflation-adjusted to the vintage year, estimate |
| `state` | — | FIPS code of the state, appended by the service |
| `county` | — | FIPS code of the county within the state, appended by the service for county rows |

### Catalog facts

- Availability: Source only · intended for 0.31
- Domain: Demographics
- Spatial resolution: Detailed tables are available down to the block group; usdata selects states and counties
- Temporal resolution: Five-year period estimates, one vintage per year
- Updates: Released once a year; the 2020-2024 estimates were released on 8 January 2026
- Terms of use: <https://www.census.gov/data/developers/about/terms-of-service.html>
- Citation: U.S. Census Bureau, American Community Survey 5-Year Estimates, Detailed Tables, Census Data API, accessed via usdata
- Coverage: not specified in the catalog
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.census.gov/data/developers/data-sets/acs-5year.html)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.census.acs:Acs5Year`
