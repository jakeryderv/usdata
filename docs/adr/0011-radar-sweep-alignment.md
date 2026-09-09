# 0011: Explicit radar selection and record alignment checks

Status: accepted. Date: 2026-09-09.

## Context

Matching Storm Events report 1184052 to a nearby KTLX observation selected
`KTLX20240507_044053_V06` (SHA-256
`0599ac838bd27cb3c79be0eea057229720109e4da03911683602cd50f357133e`).
With xradar 0.12.0, whole-volume decoding fails with conflicting azimuth lengths.
Sweep 14 has no end marker before sweep 15 starts. The backend retains its moment
header but omits it from the coordinate list and data dictionary. Later groups
index coordinate entries by the original sweep number, pairing observations with
another sweep's coordinates. Some shifted sweeps have equal lengths, so merely
catching shape errors is insufficient. Padding or dropping incomplete sweeps
does not repair the interior omission. Sweep 0 is unaffected.

## Decision

Expose the backend's integer/list sweep selection through `FetchedAsset.open`.
Accept distinct, nonnegative, zero-based integer indices; retain original group
names and record returned groups alongside unchanged source provenance.

Before decoding, inspect xradar's parsed metadata without loading moment arrays.
For every requested sweep (all moment headers by default), compare the moment
header with the data start record, then compare the coordinate record sequence
with the data record range excluding non-radial messages. These messages may
occur within a sweep or after the last received ray of an incomplete final
sweep; they must not cause a false alignment failure. Reject missing or mismatched
entries with `RadarDecodeError`. Close the metadata reader on success or failure.
Decode and eagerly load only after the complete requested selection passes.

Do not patch xradar globally, silently discard groups, or infer missing end
markers. Padding remains appropriate for incomplete sweeps with aligned metadata.
An explicitly requested unaffected sweep remains usable. A damaged legacy
fixture reproduces the interior omission offline, including an equal-ray-count
mismatch; the live event-context notebook exercises the original modern volume.

## Consequences

The guard depends on xradar's NEXRAD metadata representation, including record
numbers. Dependency upgrades must preserve the regression tests or prompt a
review of this compatibility layer. It parses the archive an extra time and
still reads the whole input, but limits decoded arrays when selecting sweeps.
This is a bounded alignment check, not general radar validation or a repair for
the affected full volume. An upstream reconstruction fix should be evaluated
against the pinned volume before relaxing the guard. No provider, cache, shared
model, or core dependency changes are needed.

See [xradar's selection API](https://docs.openradarscience.org/projects/xradar/en/stable/generated/xradar.io.backends.nexrad_level2.open_nexradlevel2_datatree.html)
and the related [sparse-sweep issue 356](https://github.com/openradar/xradar/issues/356).
That issue's sparse-key fix does not establish coordinate alignment for this
file. The notebook keeps event/time matching and projection choices explicit
until repeated workflows justify a shared research API.
