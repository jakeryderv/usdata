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
version, and for each asset its resolved URL, checksum, request `properties`,
and provenance.

For a source that needs a key, the sidecar's `credentials` field names the
environment variables the source requires, such as `USDATA_AQS_EMAIL` and
`USDATA_AQS_KEY`, and never their values. No key appears in the source URL,
the lockfile, or the cached file. Where a service's response echoes the key or
changes between identical requests, the adapter writes a canonical form of it
and says how in `transformations`, so the checksum can pin it. See
[ADR 0039](https://github.com/jakeryderv/usdata/blob/main/docs/adr/0039-credentialed-sources.md).

### Files fetched as byte ranges

An asset fetched as part of a larger object, today the HRRR and GFS `messages`
parameter, records five more fields plus one line under `transformations`. The
checksum and size still describe the local file, which is the selected GRIB2
messages concatenated:

| Field | Meaning |
|---|---|
| `index_url` | The `<key>.idx` sidecar the byte ranges were resolved through. |
| `index_checksum` | `sha256:<hex>` of that index text as it arrived. |
| `ranges` | The inclusive `start` and `end` byte pairs that were fetched, in order. |
| `selectors` | The index selector each of those ranges was fetched for, in the same order. |
| `object_size` | Size of the whole object when the ranges were resolved. |
| `object_etag` | The ETag that object carried, re-sent as `If-Match` on every later request. |
| `transformations` | One entry, `grib2 messages 105,131 concatenated from <object url>`. |

```json
"ranges": [
  { "start": 64292396, "end": 65005961 },
  { "start": 96828629, "end": 97953522 }
],
"selectors": ["CAPE:surface", "HLCY:3000-0 m above ground"],
"object_size": 150114757,
"object_etag": "17ef4503533b3bd3b4c6338b7dddcf2c"
```

A whole-file sidecar is unchanged: the new fields are optional, an older
sidecar loads with `ranges` empty and the rest unset, and the lockfile schema
is the same. The asset's URL carries the selection as a fragment,
`...wrfsfcf00.grib2#messages=105,131`, so the lockfile entry alone says which
bytes were taken and from where.

Those numbers, 105 and 131, are the source object's own: the one-based message
numbers its `.idx` sidecar publishes, and the readers surface them as
`object_index`. The fetched file holds the same two messages at positions 0 and
1, which is what `usdata inspect` prints and what the readers call `file_index`.
The recorded `selectors` name the same two messages a third way, in the index's
own vocabulary, and `Grib2Summary.variable_for` turns one of those back into the
variable name the reader gives it. See
[ADR 0028](https://github.com/jakeryderv/usdata/blob/main/docs/adr/0028-partial-grib2-fetch-through-index-files.md).

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

A locked restore downloads each pinned URL without repeating discovery. An
entry with `ranges` re-issues exactly those ranges against the pinned ETag,
one request per contiguous run, and never reads the index again, so a
republished index cannot move a pin. When the bytes differ from the pin,
restoration continues through the remaining entries, then exits 4 listing every
asset that changed. A range request that is refused, whether because the
object was republished (HTTP 412) or because the server answered with the whole
object or a `Content-Range` that does not match the request, and a pinned URL
that answers 404 or 410, are reported the same way, as drift a configured
mirror may repair; nothing is written for them. Assets that still match
are restored; changed ones keep whatever file was already at that path; the
lockfile is not rewritten. In Python, `pull()` raises `UpstreamChanged`, whose
`drift` lists each asset.

## Restoring from a mirror

A checksum cannot recover bytes, but a mirror that stores bytes *by* their
checksum can. Set `USDATA_MIRROR_URL` to the base URL of one, and a locked
restore tries the mirror for each pinned URL that no longer reproduces its
pin: it fetches `<mirror>/sha256/<hex>`, the hex of the checksum the lockfile
already records, verifies the bytes against that same pin, and writes the file.
Upstream is always tried first, so the mirror never hides a change; the
command lists such assets as `mirrored`, says on stderr that the source moved
on, and exits 0. In Python, `PullResult.mirrored` names them.

The lockfile is untouched, because the pin still describes the source. The
provenance sidecar written beside the file gains one field, `mirror`, holding
the mirror object that served it, and a new `retrieved_at`; every other field
is the pinned record. An asset the mirror cannot supply, or supplies with the
wrong checksum, stays drift, reported with the reason appended:
`upstream changed; not mirrored (404)`.

The project mirror at `https://data.usdata.dev` holds exactly the objects the
committed example lockfiles pin, written by the weekly restore job and kept
while any committed lockfile references them, so it restores the shipped
examples and nothing else. The layout is one directory of files named by
hash, which any static host can serve; a manifest of your own gets the same
guarantee from a mirror you run behind the same setting. The SDK never
uploads. See [ADR 0030](https://github.com/jakeryderv/usdata/blob/main/docs/adr/0030-content-addressed-mirror.md).

A source whose credentials are not set is never asked. A locked restore takes
each of its entries from the cache, or from the mirror when one is configured,
and reports those as `mirrored` with a note that upstream was not checked for
changes; `PullResult.unchecked` names them. Only an entry that neither can
supply fails, with the variables to set. Resolving, `--update`, and `--force`
always need the key.

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
