# FEMA

Provider id `fema`. Homepage: https://www.fema.gov/

## Access notes

[OpenFEMA](https://www.fema.gov/about/openfema/api) is an anonymous REST API
with an OData-style grammar: `$filter`, `$orderby`, `$top`, `$skip`, `$select`,
`$inlinecount=allpages`, and `$format=csv`. No key or account is needed. The
service returned 10,001 rows when asked for them and ignores `$top=0`, so a
page size is a choice rather than a cap, and a count is asked for with `$top=1`.

A timestamp in a `$filter` must be a date alone: a full timestamp is compared
against its own percent-encoded text and matches nothing, with no error. Check
the filter echoed in the response `metadata` when a query comes back empty.

FEMA's rows are keyed by state and county FIPS codes and carry no coordinates,
so its datasets are selected by a named place, not a box
([ADR 0034](../adr/0034-query-keeps-the-resolved-place.md)).
Dataset and field metadata, including each dataset's `lastDataSetRefresh` and
`recordCount`, are themselves served at `/api/open/v1/OpenFemaDataSets` and
`/api/open/v1/OpenFemaDataSetFields`. The
[terms and conditions](https://www.fema.gov/about/openfema/terms-conditions) ask
for the endpoint and its version, the time of access, and a disclaimer, which
`usdata cite` prints.

- [Disaster declarations](fema-disaster-declarations.md): `fema:disaster-declarations`.

Other entries from this provider are planned.

--8<-- "_snippets/planned-datasets.md"

## Datasets

See the [generated dataset catalog](../generated/catalog/fema.md) for status, capabilities, endpoints, and versions.
