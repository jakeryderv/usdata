# 0043: Assets carry the request facts their bytes do not state

Status: accepted. Date: 2026-09-25. Extends
[ADR 0027](0027-provider-contract.md).

## Context

Several sources answer a request with a file that does not say what the
request asked for. An NCEI Access Data Service CSV (GHCN-Daily, GSOM, GSOY,
LCD, climate normals) has no units row, so whether `PRCP` is millimetres or
inches depends on the request's `units`. A CO-OPS CSV carries no station, datum,
units, interval, bin, or time zone. Eight notebooks recorded the same friction:
the manifest "has to travel with the data"
([issue 334](https://github.com/jakeryderv/usdata/issues/334)).

The facts exist in two places, and the reader can use neither. The manifest is
not available where a file is opened. The source URL's query string holds them,
but reading it would put each adapter's parameter names into the reader, and
the URL's spelling is the agency's, not a promise.

`Asset` has no place for them. It carries identity, location, media type,
size, checksum, time, and box, all of it about the object rather than the
request that shaped it.

## Decision

`Asset` gains `properties`, a mapping of string keys to string values, empty by
default. `list_assets` records there the facts of the request that the fetched
bytes do not state and that change how the bytes read: the unit system, datum,
station, interval, bin, or time zone the request fixed. It is the STAC notion of
properties, kept as flat strings so a lockfile stays plain JSON.

Keys are lowercase snake case and name the fact, not the agency's parameter:
`units`, `datum`, `station`, `interval`, `bin`, `time_zone`. Values are the
source's own vocabulary, such as `metric`, `standard`, or `english`, since the
guide for each source already says what those mean. An adapter records only
what the bytes leave out. The NCEI CSVs name their stations in a column, so
those adapters record `units` alone, while CO-OPS records every request fact.

The core does nothing with `properties` but keep them. They are part of the
asset, so a lockfile pins them and a restore hands them back without asking the
adapter. Every reader copies them into `attrs["usdata"]["properties"]`, beside
the asset id and provenance it already copies, and always as a mapping, empty
when the asset has none.

They go under `attrs["usdata"]`, not `attrs["units"]`. `attrs["units"]` holds
units the file states, column by column, as the ERDDAP and IBTrACS units rows
give them. A unit system the request chose is a different kind of fact about
where the bytes came from, and it sits with the rest of that record.

Credentials never appear in `properties`, as they never appear anywhere else in
an asset ([ADR 0039](0039-credentialed-sources.md)). The contract checks
already search every listed asset's JSON for a leaked key, so they cover the
new field without change.

## Consequences

A frame opened from an NCEI or CO-OPS CSV says which unit system, datum, and
station it holds, whether it was fetched just now or restored from a lockfile,
and whether it was opened with `open()` or `open_csv()`.

The lockfile schema gains an optional field. Older lockfiles have none, so their
assets restore with empty `properties` until a forced pull re-resolves them;
nothing about their pins changes. A lockfile written now lists `properties` on
every asset, empty for sources that record none.

The provider contract grows by one field an adapter may fill. An adapter that
leaves it empty is unaffected. `properties` is not a query: it is not matched,
compared across pulls, or used to decide a cache hit, so an adapter can add a
key later without invalidating anything already cached or pinned.

`usdata inspect` of a cached path without its fetch result reads only the
provenance sidecar, which does not carry `properties`. Recording them there as
well would change the sidecar schema, and nothing yet needs it.
