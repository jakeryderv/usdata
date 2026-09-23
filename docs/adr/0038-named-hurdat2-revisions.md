# 0038: A HURDAT2 query can name a revision, and the reader stays strict

Status: accepted. Date: 2026-09-23. Extends
[ADR 0020](0020-hurdat2-whole-file-and-format-reader.md).

## Context

ADR 0020 resolves the newest revision in the NHC listing and has the reader
raise on a malformed line rather than return a partly parsed table. Typos in
archived revisions were tolerable under that rule because the next revision of
the same span corrected them. The Atlantic revision of 2026-09-12 broke that
assumption for the newest file: it has a latitude and longitude with no comma
between them (`63.3N    7.5E`) and a latitude written `38.83`, neither present
in the 2026-02-27 revision. The first could be split unambiguously; the second
could be `38.8N` or `38.3N`. With no way to select anything but the newest file,
a first pull of `noaa:hurdat2` could not be opened, and the weekly live checks
and the storm-surge example failed.

## Decision

Add an optional `revision` parameter: a calendar date, typed or ISO text,
compared with the date parsed from each filename of the requested basin. When
set, it replaces "newest revision" and keeps "newest span" among files that
carry that date. A date that no listed file carries is a `QueryError` naming the
newest revisions, never a fallback.

Keep the reader strict. Do not repair either typo, not even the unambiguous
one: repairing one kind and raising on the other would still leave the newest
file unreadable, and every repair rule is a place where a future typo parses
silently. Instead the reader's error names the asset and points at `revision`.

The examples and the parsing live check name the last readable Atlantic
revision. A second live check keeps resolving and downloading the newest one,
so listing or naming changes still surface.

## Consequences

A manifest can now choose its HURDAT2 revision before any lockfile exists, which
also makes a first pull repeatable when the NHC publishes mid-project. Moving an
example to a newer revision is now a manifest edit as well as a
`pull --update`. Nothing notices automatically when the NHC corrects the file;
the pinned examples keep reading 2026-02-27 until someone moves them. Typos
are reported upstream rather than worked around.
