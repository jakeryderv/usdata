# 0047: A partial fetch records a selector for every field it fetched

Status: accepted. Date: 2026-09-28. Extends [ADR 0028](0028-partial-grib2-fetch-through-index-files.md)
and [ADR 0046](0046-listing-grib2-messages.md).

## Context

A partial fetch records one index selector per byte range, and the reader and
`Grib2Summary.variable_for` pair each message on disk with the selector at its
position. RAP breaks that one-to-one: it packs the U and V wind components of a
level into one GRIB2 message, which its index numbers `92.1` and `92.2` at one
offset. A byte range cannot split the message, so naming either field fetches
both, and both fields then carried the one selector that fetched them. Since
v0.29.0 `variable_for` refuses that case rather than return the wrong variable
([issue 354](https://github.com/jakeryderv/usdata/issues/354)), which left the
wind components of RAP, the one model that packs them, with no lookup at all.

## Decision

`PartialFetch` and `Provenance` gain `field_selectors`, one list per selected
message naming each field it holds, in the index's field order. A field a
selector named carries that selector's text under the rule `selectors` already
follows; a field fetched only because it shares the message carries its index
line's own selector, such as `UGRD:500 mb:anl`. The reader and `inspect` give
the k-th field of a message on disk the k-th text, so every field has its own
`selector` and `variable_for` answers for each of them.

The pairing relies on ecCodes yielding a message's fields in the order the
index numbers them. That held for RAP's `awp130pgrb` analysis on 2024-05-06
at 500 hPa and 10 m, U before V in both, and a live check keeps asserting it.

`selectors` is unchanged and still written. The field is additive: a lockfile
or sidecar written before it loads with it empty, restores through the same
ranges, and pairs every field of a message with that message's one selector
as before, so `variable_for` still refuses to guess for such a file.

## Alternatives

- **Only for multi-field messages.** Recording one text for a single-field
  message duplicates `selectors`, but a list that is sometimes present and
  sometimes not per message is harder to read than one that always is.
- **Replace `selectors`.** Cleaner, but it would change what existing
  sidecars and lockfiles mean for no gain on the files they describe.
- **Look the fields up in the index at read time.** A read never touches the
  network, and the index may have been republished since the fetch.

## Consequences

MRMS, the other naming friction in issue 331, is left as it is. Its variable is
the product without the nominal-height suffix of the directory name, each file
holds that one variable, and the MRMS guide and the reader reference now say
so rather than add a lookup for a file that has nothing to look up.
