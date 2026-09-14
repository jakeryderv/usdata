# Provenance and drift

Every file usdata fetches gets a sidecar beside it in the cache, and every
lockfile pins a checksum. Together they answer two questions a reviewer will
ask: where did this input come from, and is it still the same file?

## What is recorded

A provenance sidecar records the source URL, provider and dataset ids, the
retrieval time, the byte count, the SHA-256 checksum, and the license. It
describes the source bytes, not any analysis you do afterward. When a reader
opens the file, a copy of the sidecar travels with the result in
`frame.attrs["usdata"]` or `dataset.attrs["usdata"]`, but pandas and xarray
operations can drop attributes, so the sidecar and the lockfile remain the
persistent record.

A lockfile records the manifest's checksum, when it was generated, the usdata
version, and for each asset its resolved URL, checksum, and provenance.

## What a checksum can and cannot do

A checksum proves that the bytes you have are the bytes that were pinned. It
cannot recover bytes that are gone. Query-based services revise observations
and page membership without exposing old versions; file archives replace a
revision and eventually delete the old one. If both the cached copy and the
upstream version disappear, usdata cannot recreate the file. This is why the
cache belongs with the manifest and lockfile for any work that must be
reproducible later. The cache stores one current file per asset id; it is not
a versioned archive.

## How drift is reported

A locked restore downloads each pinned URL without repeating discovery. When
the bytes differ from the pin, restoration continues through the remaining
entries, then exits 4 listing every asset that changed. Assets that still match
are restored; changed ones keep whatever file was already at that path; the
lockfile is not rewritten. In Python, `pull()` raises `UpstreamChanged`, whose
`drift` lists each asset.

## Accepting a change

Name the entries whose new bytes you accept, by asset id from the report or by
dataset id:

```sh
usdata pull dataset.yaml --update noaa:ghcn-daily
```

`--update` re-downloads only the selected entries from their pinned URLs and
rewrites only their checksums and provenance. Discovery is not re-run, so
listing-based sources keep the same files. Entries whose bytes turn out to be
unchanged keep their existing pin, so the lockfile diff shows only real
changes. Every unselected entry must still match; otherwise the run exits 4
and nothing is rewritten. `--update` cannot be combined with `--force` and
needs an existing lockfile. In Python, pass `update=["noaa:ghcn-daily"]`.

Use `pull --force` instead when the query itself should change, for example to
move to a newer revision of a whole-file archive. That re-resolves everything.

## Which sources revise

Every source usdata serves revises. Station services re-verify observations,
model and satellite archives are stable but can be republished, whole-file
archives such as Storm Events, SPC, and HURDAT2 replace files in place or by
revision date, and tide predictions change when NOAA updates a station's
harmonic constituents. The provider notes for each dataset say how and how
often.
