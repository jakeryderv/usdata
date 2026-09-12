# 0020: HURDAT2 as one whole file per basin with a format reader

Status: accepted. Date: 2026-09-12.

## Context

The National Hurricane Center publishes the HURDAT2 best-track database as two
plain-text files, Atlantic and northeast/north-central Pacific, in one Apache
directory that also keeps past revisions — 41 HURDAT2 data files on 2026-09-12, the oldest
revised 2017-04-13. How deep that archive runs is the NHC's choice and it is not
a complete history: revisions older than the ones listed are simply gone.
Filenames embed the data span and a revision date in `MMDDYY` or `MMDDYYYY` form,
occasionally with a trailing letter, and the Atlantic basin token is sometimes
absent. There is no records
API, no per-storm file, and no server-side subsetting of any kind. The format is
also unlike anything usdata already reads: storm headers declaring a track-point
count, followed by that many fixed-position lines with hemisphere-suffixed
coordinates and several missing-data sentinels.

Every previous dataset let a query narrow what was downloaded. Here nothing can,
so the useful work is turning one whole file into an analyzable table.

## Decision

Expose one asset per basin, selected by a `basin` param (`atlantic` by default,
`pacific`). Resolve the directory listing to the newest data span and then the
newest revision of that span, parsing revision dates rather than sorting names as
text. Ignore other basins, unparseable dates, and non-local links. Keep the
complete filename as the stable asset ID and preserve the original bytes; leave
asset size unknown because the listing reports approximate sizes. Reuse the
Storm Events pattern (ADR 0010) for listing, whole-file fetch, and lockfile
pinning; capabilities stay false.

Reject dates instead of accepting them as informational bounds. Every revision
holds the complete record for its basin, so a requested window selects nothing,
and copying it into asset time bounds would misdescribe the cached file in the
lockfile and provenance sidecar. Asset time bounds report the data span named in
the filename. Reject geographic filters, variables, text queries, and unknown
params for the same reason: nothing about the download changes.

Add a `hurdat2` reader behind the existing pandas extra (ADR 0006), in its own
private module beside the NetCDF and radar readers. Infer it from the dataset id
or a `hurdat2-*.txt` asset ID, since the service serves `text/plain` and media
type alone cannot identify the format. Return one row per track point with
`storm_id`, `name`, UTC `time`, record codes, signed decimal coordinates, wind,
pressure, the twelve wind radii, and the radius of maximum wind. Convert the
documented sentinels (`-999`, and `-99` for a maximum wind left unassigned on a
non-developing depression) to NaN, normalize longitudes into [-180, 180], use
float dtype so the gaps are representable, and encode units in column names
rather than synthesizing a units map. Validate declared track-point counts, field
counts, timestamps, coordinates, and measurements, raising `Hurdat2FormatError`
with the offending line instead of returning a partly parsed table. Reject the
CSV options, as the NetCDF and radar readers already do.

## Consequences

A caller interested in one storm still downloads about 7 MB (Atlantic) or 4 MB
(Pacific) and filters locally; the example and guide say so. Two basins cannot be
combined in one asset, and a manifest wanting both lists two sources. Rejecting
dates makes HURDAT2 the first adapter where a manifest's shared date range is an
error, which is deliberate: a silent no-op would be indistinguishable from a
working filter.

Revision selection depends on NHC filename conventions. A name that breaks the
span-and-date pattern is ignored rather than guessed at, which is right for the
names already in the listing: `hurdat2-atl-02052024.txt` carries no data span.
The cost is that "no file in the listing" only surfaces once no name parses, so a
convention change affecting only the newest file would leave the adapter serving
the newest name it can still read. Pinning a revision in a lockfile, not trusting
the listing, is what makes a run reproducible. When a new season's file appears
under a new name, existing lockfiles keep restoring the old one until the NHC
removes it; preserving the cache remains the durable reproducibility answer.

Accepting 20- as well as 21-field data lines, and longitudes written in the
unwrapped 0-360 west convention, is what keeps archived revisions readable rather
than merely downloadable: `max_wind_radius_nm` is NaN before 2021, and a point
written `358.0W` reads as `2.0`, the value the NHC itself later published for it.
The cost is a looser format check: with the longitude bound raised from 180 to
360, a transposition such as `290.2W` for `209.2W` now parses silently as `69.8E`
where it would once have raised. That is accepted because the unwrapped form is
real and continuous in the archive — `AL061966` drifts from 305.0W to 299.0W
without a break — so no bound can separate it from a typo of the same magnitude.
Of the 41 files the directory listed on 2026-09-12, 39 parse; the two that do not
carry an upstream typo, a missing comma and a date of `C0091018`, each fixed by
the next revision of the same span. Refusing those is the point of the format
error. Column names, not attributes, carry units, so exports keep them.
Scientific interpretation is unchanged by this decision:
the reader does not correct the reanalysis's era-dependent undercounting, does
not reconstruct a wind field from quadrant radii, and does not merge basins.
IBTrACS remains a separate planned entry for global merged tracks.
