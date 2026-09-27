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

That makes Census a credentialed source. Its geography is a state or county
FIPS code (`for=county:113&in=state:40`), so it selects by place, not by box
([ADR 0034](../adr/0034-query-keeps-the-resolved-place.md)). `census:acs-5year`
is selected on the [roadmap](../roadmap.md)
([issue 379](https://github.com/jakeryderv/usdata/issues/379)), with its rules
in [ADR 0045](../adr/0045-acs-5year-selection.md).

Checked with a key on 2026-09-27, against `acs/acs5` vintages 2021 to 2023:

- The response is a JSON array of arrays with a header row. Every value is a
  string, and the geography columns follow the requested variables. It holds no
  copy of the key, and identical requests return identical bytes.
- A request takes at most fifty variables, `NAME` included; the fifty-first is
  `400` with `error: 'get' is limited to 50 variables`.
- An unknown variable is `400` with a plain-text message, and an unknown vintage
  is a `404` HTML page. A missing or invalid key is a `302` to `missing_key.html`
  or `invalid_key.html`. A geography the vintage lacks is `204` with an empty
  body.
- Connecticut is keyed by its eight old counties through vintage 2021 and by its
  nine planning regions from vintage 2022.
- Margins of error and some estimates are negative
  [annotation codes](https://www.census.gov/data/developers/data-sets/acs-1year/notes-on-acs-estimate-and-annotation-values.html),
  such as `-555555555` for a controlled estimate.

--8<-- "_snippets/planned-datasets.md"

## Datasets

See the [generated dataset catalog](../generated/catalog/census.md) for status, capabilities, endpoints, and versions.
