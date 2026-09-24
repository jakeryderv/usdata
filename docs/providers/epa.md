# EPA

Provider id `epa`. Homepage: https://www.epa.gov/

## Access notes

The [AQS Data API](https://aqs.epa.gov/aqsweb/documents/data_api.html) is the
first source in the catalog that needs credentials. Every request carries an
`email` and a `key` as query parameters. The key is free, issued by email when
the address is registered through the API's own `signup` endpoint, and there is
no web form. usdata reads the two from `USDATA_AQS_EMAIL` and `USDATA_AQS_KEY`
and keeps them out of everything it writes
([ADR 0039](../adr/0039-credentialed-sources.md)).

EPA asks callers to send one request at a time, at most ten a minute, with a
pause between them, and may disable an account that does not. Responses are
slow, and each one echoes the full request, key included, in its header.

- [AQS daily summaries](epa-aqs-daily.md): `epa:aqs-daily`.

## Datasets

See the [generated dataset catalog](../generated/catalog/epa.md) for status, capabilities, endpoints, and versions.
