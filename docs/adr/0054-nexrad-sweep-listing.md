# 0054: NEXRAD sweeps are chosen from a metadata listing and opened by index

Status: accepted. Date: 2026-10-08. Extends
[ADR 0011](0011-radar-sweep-alignment.md) and
[ADR 0042](0042-one-open-method-per-format.md).

## Context

`open_nexrad(sweep=...)` takes zero-based positions in the volume. A study that
wants the same scan from every volume, such as the lowest-angle velocity, cannot
name it that way: split cuts scan each low angle twice, once for reflectivity
and the dual-polarization moments and once for velocity, and SAILS and MRLE
insert rescans. In `KTLX20240507_021123_V06`, VCP 212 with three SAILS cuts, the
0.48° angle is sweeps 0, 1, 4, 5, 9, 10, 16, and 17, and another VCP puts other
angles at those indices. Learning the angles by decoding the whole volume costs
far more than the selection is worth.

xradar's metadata pass, which the alignment check of ADR 0011 already runs,
holds what a selection needs: each sweep's VCP cut number, the VCP table's angle
and SAILS and MRLE flags for that cut, the data blocks present, and each ray's
collection time. On that volume it takes 1.4 s, against 3.3 s to decode one
sweep.

Four shapes were weighed: a listing with selection left to the caller; an
`elevation=` and `moment=` option on `open_nexrad`; both; and a documented
recipe with no API.

## Decision

**A listing, and selection stays by index.** `readers.nexrad_sweeps(path)`
returns one `NexradSweep` per sweep, read from metadata only: `index`,
`elevation_number`, `fixed_angle`, `moments`, `start`, `end`, `rays`,
`complete`, `sails`, and `mrle`. `FetchedAsset.inspect()` returns the same list
with the VCP number as a `NexradSummary`, the way it returns a GRIB2 file's
messages, and `usdata inspect` prints it as a table. The caller chooses there
and passes indices to `open_nexrad`, whose signature does not change.

**The listing says what `open_nexrad` returns.** `fixed_angle` is the value the
decoder puts in `sweep_fixed_angle`, `moments` are named as the decoder names
them, and a legacy volume's spectrum width, which xradar 0.12 reads but drops
under a block name its own table does not match, is left out. A test compares the listing with the
decoded fixtures sweep by sweep.

## Alternatives

- **`open_nexrad(elevation=..., moment=...)`.** It needs an angle tolerance,
  and it would still return every SAILS repeat, leaving the caller to choose
  among them by time. Which scan a study wants, the first of the volume or
  every rescan, is analysis policy, not reader behaviour.
- **Both.** The shortcut is a few lines over the listing; it can be added later
  without breaking anything if studies keep writing them.
- **A recipe only.** Every analysis would decode a whole volume to learn its
  angles.

## Consequences

Selection code reads the same in every VCP, and choosing costs one metadata
pass. The listing depends on xradar's metadata tables, as ADR 0011's check
already does, so an xradar upgrade must keep the cross-check test passing.
