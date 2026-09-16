# 0028: Partial GRIB2 fetch through index files

Status: accepted. Date: 2026-09-15. Extends [ADR 0002](0002-anonymous-s3-over-https.md),
[ADR 0018](0018-selective-lockfile-updates.md), and [ADR 0022](0022-grib2-reader-backend.md).

## Context

A HRRR surface analysis is 150 MB and a GFS 0.25 degree file is 508 MB. Both
hold a few hundred messages, and the questions the worked examples ask need two
or three of them: surface CAPE and 0-3 km helicity near a tornado report. Every
byte of the rest is downloaded, hashed, cached, and thrown away by the reader's
`select`. The registry has said so since [ADR 0026](0026-one-registry-schema.md),
which added `partial_fetch` as a field to flip rather than a schema to change.

NCEP publishes a wgrib2 index beside every object. Verified on 2026-09-15:
`hrrr.20260914/conus/hrrr.t12z.wrfsfcf01.grib2.idx` is 10,176 bytes and 170
colon-delimited lines with no length field.

```
71:43023331:d=2026091412:TMP:2 m above ground:1 hour fcst:
72:44188209:d=2026091412:POT:2 m above ground:1 hour fcst:
```

The fields are the message number, its byte offset, the run stamp, the wgrib2
short name, the level text, and the step text. A message's length is the next
offset minus its own, and the last message runs to the end of the object.

The objects answer range requests. That HRRR object is 151,717,165 bytes with
`Accept-Ranges: bytes` and ETag `81198a73ad430c73adfbe3335421ea99`;
`Range: bytes=43023331-44188208` returned 206, `Content-Range: bytes
43023331-44188208/151717165`, and 1,164,878 bytes that begin `GRIB`, declare
edition 2, carry a section 0 length equal to the range width, and end `7777`.
The open-ended tail range `bytes=150260355-` returned 206 and 1,456,810 bytes,
also `GRIB`. A concatenation of whole messages is a valid GRIB2 file, and
`_grib._messages` already walks section 0 lengths, so the reader needs no new
decoding path. The 2026-09-14 GFS 0.25 degree f003 object behaved the same:
40,474 bytes of index over 743 lines, and `bytes=421683537-422194644` returned
206 and 511,108 bytes beginning `GRIB`. GFS keys carry no extension, so the
sidecar is `<key>.idx`.

Two upstream facts constrain any design. A multi-range request
(`bytes=43023331-44188208,0-377041`) returned **200 and the whole
151,717,165 byte object**: S3 serves no `multipart/byteranges`, and a client
that assumes otherwise silently downloads everything it was trying to avoid.
And the index is a separate object with its own ETag, written seconds after the
one it describes, so nothing guarantees the two stay in step across a
republication.

## Decision

Three things are settled here.

**Identity.** The selection lives in the asset's href as a fragment naming the
resolved message numbers in ascending order, `#messages=71,170`, with a digest
of that list inserted into the asset id: `hrrr.20260914.t12z.wrfsfcf01`
becomes `hrrr.20260914.t12z.wrfsfcf01.part-<12 hex>.grib2`. Numbers are
recorded, not the selectors a user wrote, so identity never depends on reading
the index again and two runs of the same query produce the same cache path.
`Asset` gains no field and the lockfile schema does not change: `LockedAsset`
already requires the href to equal `provenance.source_url`, so the fragment
carries the whole identity into a restore.

**Pinning.** One sha256 over the concatenated bytes, which is what
`Asset.checksum` and `Provenance.checksum` already mean, plus the resolved byte
ranges recorded in the provenance sidecar alongside the index URL, the sha256
of the index text as fetched, and the object's size and ETag. A restore
re-issues exactly those ranges, one GET per contiguous run, requires 206,
validates `Content-Range` against the request and the recorded size, sends
`If-Match` with the pinned ETag, concatenates, and compares the checksum. It
never reads the index, so a republished index cannot move a pin. Per-range
checksums were considered: they localise drift to one message, but they add a
lockfile field and change nothing about what a restore does.

**Reader.** `open_grib2` treats a file whose provenance carries the
partial-fetch `transformations` entry as already selected, so the
several-messages-need-`select` guard does not apply and every message loads.
Message iteration is unchanged, and `select` still narrows a partial file.

Also settled: `messages` accepts the index's own vocabulary, short name and
level text with an optional step text, not the ecCodes `shortName` and
`typeOfLevel` the reader's `select` uses. The two vocabularies differ (`TMP`
against `2t`), and the mapping between them is a table this adapter has no
business owning. Selection happens at listing time, where the index is
available and identity has to be fixed, so a reader-level `select` cannot drive
it. A selector that matches nothing raises `QueryError` naming it, and an
absent or unparsable index raises `QueryError` naming the object: never a
silent fall back to the whole file, which would turn a 1 MB request into 151 MB.

`partial_fetch` becomes true for `noaa:hrrr` and `noaa:gfs` only. It promises
that a caller can ask for a byte subset which is itself a valid file of the
declared media type, and that the pinned checksum covers exactly those bytes.
The contract tests read it as a statement about the query surface: a dataset
declaring it must declare a `messages` parameter, and one that does not must
not.

## Alternatives

- **One multi-range request per object.** The obvious saving, and the reason
  the probe above exists. S3 answers it with the whole object and a 200, so a
  client would have to detect that and discard 151 MB. One GET per contiguous
  run is the only shape the service supports.
- **Server-side subsetting.** NOMADS offers a `filter_hrrr_2d.pl` CGI that
  returns selected fields. It is a different service with its own availability,
  rate limits, and retention, and it is not the bucket this adapter reads
  ([ADR 0002](0002-anonymous-s3-over-https.md)). The bucket plus its index is
  the canonical layout.
- **Pinning message numbers and re-reading the index on restore.** Smaller
  sidecar, but it makes reproduction depend on a second object that is
  republished independently. Recording the ranges makes a restore one kind of
  request against one object.
- **Reusing the reader's `select` for the request.** It would spare the user a
  second vocabulary, at the price of a name mapping maintained per model inside
  the adapter, and it would move selection after listing, where the asset id is
  already fixed.
- **Sharing one id between a whole file and a subset of it.** Tempting for the
  cache, but the two are different bytes with different checksums, and a
  lockfile that pins one must never be satisfied by the other.

## Consequences

The severe-weather questions the examples ask cost about 1% of what they cost
today: two HRRR messages are 1.8 MB against 150 MB. A manifest pins them the
same way it pins whole files, and `verify` is unchanged.

Every partial listing costs two extra requests per object, a HEAD for the size
and ETag and a GET for the index, which is why `messages` is opt-in and
whole-file behaviour is byte-identical without it. A fetch now depends on the
object not being republished between listing and download; `If-Match` turns
that race into a loud 412, which a restore reports as drift the way
[ADR 0018](0018-selective-lockfile-updates.md) reports changed bytes. A
response that is not 206, or whose `Content-Range` disagrees with the request,
fails before a byte is written rather than producing a file that is not what
was asked for.

The byte ranges have to reach `fetch` from wherever they were resolved.
`Provider` gains one optional method, `prepare_fetch`, which the core calls
immediately before `fetch` and whose return value it records; a restore passes
the pinned record in, and the adapter rebuilds the ranges from it. Adapters
that fetch whole objects inherit the default and never see it.

Out of scope: server-side grid subsetting, index dialects beyond HRRR and GFS,
MRMS, GOES and NEXRAD, a whole file and a subset sharing an id, and parallel or
multi-range GETs.
