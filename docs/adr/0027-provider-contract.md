# 0027: The provider contract

Status: accepted. Date: 2026-09-15. Extends [ADR 0001](0001-curated-registry-over-federated-search.md)
and [ADR 0026](0026-one-registry-schema.md).

## Context

An adapter is the unit this project grows by: one registry entry plus one
`Provider` subclass ([ADR 0001](0001-curated-registry-over-federated-search.md)).
The contract that adapter is written against is real, and it was implicit.
`Provider` and its validation helpers are public. The lifecycle every
HTTP-backed adapter inherits was `providers._http._HttpProvider`, private by
name. The coercions every parameter model uses live in `usdata.providers.params`,
which nothing exported. `QueryError` was reachable only through
`usdata.providers.base`. The checks that decide whether an adapter behaves --
listing without downloading, refusing a field before allocating transport,
fetching exact bytes to an exact path, closing only an owned client -- existed
as one parametrized test module inside this repository, so they could be read
but not run.

[ADR 0026](0026-one-registry-schema.md) made the registry entry a single typed
schema and had the contract tests verify its capability and limit claims against
the adapter. That closed the gap between an entry and its adapter for the
nineteen bundled datasets. It did nothing for an adapter written elsewhere,
which still cannot tell which of these names it may depend on, and cannot check
itself against any of it.

Entry-point discovery of third-party adapters is still deferred
([ADR 0001](0001-curated-registry-over-federated-search.md), alternatives). The
question this record answers is narrower and comes first: if someone writes a
`Provider` today, against a `Dataset` they construct themselves, what is
promised to them?

## Decision

The adapter contract is a named, published surface. It is:

- **`usdata.providers.Provider`.** The constructor taking a `Dataset`, the
  context-manager protocol and `close()`, the `params_model` and
  `accepted_params` class attributes, the validation helpers `check_params`,
  `parse_params`, `validate_params`, `reject`, and `utc_window`, and the two
  abstract methods `list_assets` and `fetch` with their documented meanings:
  listing resolves a query to assets without downloading, and `fetch` writes one
  asset to the path it is given and returns it. Added since: the optional pair
  `prepare_fetch` ([ADR 0028](0028-partial-grib2-fetch-through-index-files.md))
  and `fetch_partial` ([ADR 0032](0032-fetch-partial.md)), for an adapter that
  fetches selected byte ranges of an object; and `place_of`, with the
  `Query.place` it reads and the `place_subset` capability the checks hold it
  to ([ADR 0034](0034-query-keeps-the-resolved-place.md)), for a source keyed
  by state and county rather than by coordinates.
- **`usdata.providers.HttpProvider`.** The lifecycle HTTP-backed adapters
  inherit, renamed from `_HttpProvider` and moved to `usdata/providers/http.py`:
  the constructor's optional `client`, the `_http()` accessor subclasses call,
  and the ownership rule that an owned client is closed with the adapter while
  an injected one stays the caller's.
- **The coercions in `usdata.providers.params`.** `int_range`, `positive_int`,
  `int_list`, and `choice`, and the annotated types `StrList`, `UpperStrList`,
  and `OptionalUpperStrList`, with the values they accept and the wording of the
  messages they raise. Added since: `flag`, for a boolean the CLI passes as text.
- **`QueryError`**, raised for any query this dataset cannot satisfy, and
  **`NotImplementedProvider`**, raised for a registered dataset with no adapter.
- **`load_adapter`**, which instantiates the `Provider` a `Dataset` names.
- **The transport helpers in `usdata.protocols`.** `http.client`, `http.get`,
  and `http.download` with their shared retry policy; `s3.list_objects`,
  `s3.parse_s3_url`, `s3.https_url`, and `S3Object`; `erddap.info`,
  `erddap.axis`, `erddap.griddap_url`, `GridInfo`, and `GridSlice`; and
  `listing.directory_entries`. They carry no dataset knowledge and an adapter
  composes them.
- **The registry entry fields an adapter needs**, on the `Dataset` model an
  adapter is constructed with: `id`, `provider`, `protocol`, `domain`, `status`,
  `adapter`, `capabilities`, `limits.max_window`, and `variables`. An adapter
  reads `self.dataset` for these, and the contract checks hold `capabilities`
  and `limits.max_window` to what the adapter actually does.
- **`usdata.testing`.** `check_provider_contract`, and the individual
  `check_*` functions it composes, run those checks against any adapter, with
  the caller supplying the dataset, a factory that builds the adapter, a
  scenario query, and a client factory on a mock transport.

Everything else is internal and may change in any release: the adapter modules
under `usdata.providers.<agency>` and the constants in them, private names such
as `usdata._fetch` and `usdata._progress`, the cache layout, the on-disk shape
of the bundled registry file, and the scenario tables in `tests/`.

Changing anything in the list above is a breaking change. It needs a `breaking`
release-note fragment and the bump [versioning](../versioning.md) prescribes: a
minor release before 1.0, a major one after it, with the deprecation window
versioning describes from 1.0. Adding to the list is an `added` fragment and a
minor release. The list itself lives here; `usdata.providers.__init__` exports
it, and versioning names it as public API.

`usdata.testing` ships inside the package rather than as a separate
distribution, so the checks cannot drift from the code they describe, and it
imports `pytest` inside the functions that use it so `pytest` stays a
development dependency and importing `usdata.testing` never requires it. The
checks take transport from the caller: they install a supplied client factory as
`usdata.protocols.http.client` for their duration rather than owning a mock, so
one implementation serves a bundled adapter and an outside one.

## Alternatives

- **Leave the surface private and document by example.** The adding-a-dataset
  guide already shows the shapes. It cannot say what is stable, so an outside
  adapter either avoids the shared helpers and reimplements them, or depends on
  private names and breaks quietly.
- **Publish the contract as a separate `usdata-testing` distribution.** A
  separate package can depend on `pytest` outright, but it versions apart from
  the code it checks and is one more thing to release. The lazy import buys the
  same result.
- **Express the checks as pytest fixtures or a plugin.** A plugin would make
  `pytest` a hard dependency and an entry point a public name. Plain functions
  call from any test, including a parametrized one, which is how this repository
  already uses them.
- **Freeze the `Provider` interface now.** Premature: the path to 1.0 asks for
  two consecutive minor releases without a `Provider` change, which naming the
  surface makes visible without promising it yet.

## Consequences

An adapter maintained outside this repository can depend on named behavior and
prove it still holds, by calling `check_provider_contract` in its own suite.
`tests/adapters/test_contracts.py` keeps one test per rule per dataset and calls
the same implementation, so a rule has exactly one statement and a new rule
reaches outside adapters the moment it is added.

The cost is that these names are now expensive to change; the surface was
chosen small for that reason. `_HttpProvider` is gone rather than aliased, since
nothing outside `src/` imported it. Adapters that are not HTTP-backed still
subclass `Provider` directly, and the checks that need no transport run against
them unchanged.
