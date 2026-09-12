# 0018: Report all upstream drift and update selected lockfile pins

Status: accepted. Date: 2026-09-11.

## Context

Query-shaped assets (NCEI Access Data Service, USGS daily values, ERDDAP subsets)
pin a URL and a sha256. Agencies revise and backfill observations, so the same
URL later returns different bytes. Restore stopped at the first checksum
mismatch, so a user saw one drifted asset per run, and the only recovery was
`force`, which re-resolves every source and rewrites every pin, including the
entries that were still reproducible. Reproducibility is the product's central
promise, and this was its weakest path.

## Decision

Restore continues past upstream mismatches, restores the entries that still
match, and then raises one `UpstreamChanged` error (a `ChecksumMismatch`
subclass) listing every changed asset. The lockfile is never rewritten by a run
that ends in this error. Changed entries keep any existing cached file.

`pull` and the CLI accept `update` selectors that name an asset id or a dataset
id. Selected entries are re-fetched from their pinned URL, whatever bytes arrive
become the new pin, and only those entries' checksum and provenance are
rewritten. Entries whose bytes are unchanged keep their original record so the
lockfile diff shows real changes only. All unselected entries must still match,
so a run either succeeds completely or leaves the lockfile as it was.

`update` is distinct from `force`: it never re-runs discovery, so listing-based
sources keep the same files. `update` with `force`, without a lockfile, or with
selectors that match nothing is an input error. The lockfile schema is unchanged;
the per-entry retrieval time and checksum already record when a pin moved.

## Consequences

A stale lockfile is diagnosed in one run and repaired one entry or one dataset
at a time, with a reviewable diff. Restore may download more before failing,
because it verifies every entry rather than stopping early; those downloads are
cached when they match. A user who wants a new file selection, for example a newer
Storm Events archive, still uses `force`. Recording agency-side version metadata
where it exists, and any versioned cache, remain separate work.
