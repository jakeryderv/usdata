# 0032: Settled byte ranges are handed to `fetch_partial`

Status: accepted. Date: 2026-09-18.

## Context

[ADR 0028](0028-partial-grib2-fetch-through-index-files.md) gave `Provider` an
optional `prepare_fetch`, which the core calls immediately before `fetch` and
whose return value it records as provenance. The byte ranges still had to reach
`fetch`, and `fetch(asset, dest)` had nowhere to receive them. The model-run
adapter kept them in a dictionary on the instance and `fetch` called
`prepare_fetch` a second time to read them back.

That second call omitted the pinned record. On a restore it succeeded only
because the core's earlier call, which did carry the record, had filled the
dictionary. The contract therefore held a rule it never stated: `fetch` works
on a partial asset only after `list_assets` or `prepare_fetch` has run on the
same instance. Nothing enforced it, and the failure it invited was quiet. A
partial asset's href names the whole object with the selection as a fragment,
so a `fetch` that found no ranges had a plausible wrong answer available:
download the whole object under an id and size that describe a selection.

## Decision

`Provider` gains one optional method, `fetch_partial(asset, dest, partial)`.
The core calls `prepare_fetch`, records what it returns, and then calls `fetch`
when that was `None` and `fetch_partial` with the returned ranges otherwise.
`fetch_partial` is given everything it needs and reads nothing from the
instance, so it can run on an adapter that never listed the asset.

The default `fetch_partial` raises `NotImplementedError`. An adapter that
returns ranges it cannot fetch fails loudly, and nothing falls back to the
whole object, which would leave a provenance record naming ranges the file
does not hold.

The model-run adapter's `fetch` now refuses a partial asset with a
`ValueError` before any request, rather than looking for ranges. The
`check_fetch_lifecycle` contract check dispatches the way the core does, so an
outside adapter that settles ranges is held to the same path.

The instance dictionary stays, with a narrower job. Ranges are resolved while
listing, because an asset's id and size are derived from them, and they are
needed again at fetch. Something must carry them between those two calls.
Resolving them a second time would cost the HEAD and index GET again and would
reopen the republish race ADR 0028 closed, since the second read could see a
different index than the one the asset's id was computed from. `prepare_fetch`
reads the dictionary, or rebuilds the ranges from the pinned record when a
lockfile is being restored, and hands the result to the core. That is the only
state the adapter keeps and the only method that reads it.

This adds to the published surface of
[ADR 0027](0027-provider-contract.md) and breaks nothing in it: `fetch` keeps
its signature, and every adapter that fetches whole objects is untouched.

## Alternatives

- **`fetch(asset, dest, partial=None)`.** A breaking change to every adapter
  so that one of them can receive an argument the rest ignore. It also would
  not have removed the dictionary, for the reason above.
- **Carry the ranges on `Asset` as a field excluded from serialization.** This
  removes the adapter's state by moving it onto the shared model that lockfiles
  are written from. A field that disappears on a round trip through JSON is
  hidden state in a more central place than the one it replaces.
- **Keep the code and document the ordering rule.** Honest, but it leaves the
  quiet whole-object fallback one missing dictionary entry away.

## Consequences

Calling `fetch` directly on a partial asset was never documented and now
raises; the supported paths, `usdata.fetch`, `pull`, and the CLI, are
unchanged, as are lockfiles, provenance records, and the bytes fetched. Code
that drives an adapter by hand calls `prepare_fetch` and passes its result to
`fetch_partial`, as the core and the contract check do.
