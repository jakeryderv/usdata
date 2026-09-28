# 0046: The messages a query's files hold are listed from their index sidecars

Status: accepted. Date: 2026-09-28. Extends [ADR 0027](0027-provider-contract.md)
and [ADR 0028](0028-partial-grib2-fetch-through-index-files.md).

## Context

`messages` selects GRIB2 fields in the vocabulary of each object's wgrib2
`.idx` sidecar, `SHORTNAME:level text`, because that is what the byte ranges
are resolved through (ADR 0028). Nothing in the package listed that
vocabulary. The provider guides carry hand-made tables read from one run's
index, and the four model walkthroughs each recorded the same friction
([issue 331](https://github.com/jakeryderv/usdata/issues/331)): a selector had
to be copied from a guide or from the sidecar itself, and NBM's further texts
for ensemble spread and probability thresholds were discoverable only by
reading the raw file. `usdata info` names the parameter but not its values,
since the values belong to a run's files rather than to the dataset.

## Decision

`usdata.list_messages(dataset, query)` resolves a query exactly as a fetch
would, reads each resolved object's index, and returns one `MessageListing`
per file: the whole-file asset and one `IndexEntry` per field. An entry's
`selector` is the text that names exactly that field, so every line can be
pasted into `messages`, and its `length` is what fetching it would cost. The
CLI's `usdata messages` prints the same as one tab-separated line per field
(asset id, message number, bytes, selector) or, with `--json`, the listings.
Nothing but the index text is downloaded, and nothing is cached or recorded:
this is discovery, not an input to pin.

The adapter contract gains one optional method, `Provider.list_messages(asset)`.
Its default raises `NotImplementedError`, and `check_declared_capabilities`
requires an adapter to override it exactly when it declares `partial_fetch`,
the same flag that already requires the `messages` parameter. A promise that
parts of an object can be asked for now includes a way to learn what to ask
for. The model-run adapters implement it with the index parsing they already
use for selection, and a whole asset's listed size stands in for the HEAD a
selection makes.

`IndexEntry` moves from the NOAA index module to `usdata.models`, since the
core now returns it and must not import a provider module. Its `label`
property is renamed `selector`, which is what it is.

A query naming `messages` is refused rather than listed. The listing
describes whole objects, and silently ignoring a parameter would contradict
the contract's rule that no query field is dropped; a user checking a
selector drops it, lists, and searches the output.

## Alternatives

- **A query-aware `usdata info`.** `info` describes a dataset from the
  registry without any request. Making it list a run's files would give one
  command two jobs, one of them networked.
- **A flag on `fetch --dry-run`.** It already resolves the query without
  downloading, but its output is one line per asset, and a flag that turns it
  into one line per field inside each asset changes what the command reports.
- **Generate the guide tables from a live index.** That keeps the tables
  honest but still answers only for the run that generated them, while the
  vocabulary varies by file variant, forecast hour, and, for NBM, cycle.
- **A `--match` filter.** A listing of 170 to 743 lines is what `grep`
  exists for, and a Python caller filters a list.

## Consequences

The hand-made tables in the provider guides stay as a curated starting point
and now point at `usdata messages` for everything else. Connecting a selector
to the variable name the reader gives its message, the other half of issue
331, is unchanged by this decision: `Grib2Summary.variable_for` still does it
for a partial fetch.
