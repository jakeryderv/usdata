# Census Bureau

Provider id `census`. Homepage: https://www.census.gov/

## Access notes

Every dataset from this provider is planned; catalog entries describe the intended scope.

The [Census Data API](https://www.census.gov/data/developers.html) requires a
key on every data request. Checked on 2026-09-18: a keyless query, such as
`https://api.census.gov/data/2022/acs/acs5?get=NAME,B01003_001E&for=state:40`,
answers `302` to `missing_key.html`, which reads "A valid key must be included
with each data API request", whatever the client, vintage, or dataset (ACS 5-year
2019 and 2022 and the 2020 decennial file were tried). Only the metadata is
served without one: the dataset list at `https://api.census.gov/data.json` and
variable definitions such as `.../2022/acs/acs5/variables/B01003_001E.json`.
The API was previously usable without a key for light use, and an earlier
version of the catalog entry said so.

That makes Census a credentialed source, so it waits with the others on the
[roadmap](../roadmap.md) rather than being the next anonymous one. Its
geography is a state or county FIPS code (`for=county:113&in=state:40`), so
when it is built it selects by place, not by box
([ADR 0034](../adr/0034-query-keeps-the-resolved-place.md)).

--8<-- "_snippets/planned-datasets.md"

## Datasets

See the [generated dataset catalog](../generated/catalog/census.md) for status, capabilities, endpoints, and versions.
