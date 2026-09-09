# 0010: Storm Events annual archives and local gzip CSV reading

Status: accepted. Date: 2026-09-08.

## Context

NCEI publishes Storm Events as yearly gzip CSV files with a creation date in each
filename. Files for earlier years can be revised. The bulk directory cannot
subset records by event date, geography, or fields, and the existing public data
model has no compression field. We need reproducible downloads and local analysis
without inventing source capabilities or modifying cached bytes.

## Decision

Support the event-details table at schema v1.0. Require start/end dates, choose
whole calendar years after normalizing the bounds to UTC, and reject all spatial,
variable, text, and provider-specific selectors. Missing any requested year is
an error. All server-side subsetting capabilities are false. Annual asset time
bounds identify file years; row timestamps remain source-local dates and times.

Resolve the newest valid creation-date filename independently per year. Preserve
the complete filename as asset ID and pin its URL and compressed checksum through
the existing lockfile contract. Use exact integer directory sizes where available.
Ignore unrelated tables, unsupported schemas, and nonlocal links. Fetch bytes
through the shared HTTP transport and leave compression intact.

Use the true `application/gzip` media type. CSV inference accepts gzip media types
only with a `.csv.gz` asset ID; arbitrary gzip files require explicit reader
selection. Inside the local CSV reader, detect gzip magic and stream decompression
with the standard library. Keep pandas optional, identifier columns as source
strings, and the original archive/provenance unchanged. Add no model/schema or
public API parameters.

## Consequences

A short date range still downloads full yearly archives. Geographic/event/date
selection is explicit in the notebook, which describes local times, segmented
event records, damage ratings, and varying reporting coverage. Different source
revisions get distinct cache paths. Restoring a lockfile bypasses the directory;
missing or modified historical files remain an upstream reproducibility limit,
so users should preserve cached archives.

Reader failures propagate without changing the source. A limited `nrows` read
is not a full gzip integrity check; cache verification and lockfiles retain their
existing roles. Fatality/location tables, server-side filtered APIs, additional
schemas, and economic interpretation of damage estimates are separate work.
