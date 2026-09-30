# 0051: ArcGIS feature layers are paged by object-id range, delivered as GeoJSON, and pinned through the service's archive

Status: accepted. Date: 2026-09-29. Extends [ADR 0027](0027-provider-contract.md),
and applies [ADR 0003](0003-usgs-daily-csv-and-offset-pagination.md) and
[ADR 0035](0035-openfema-window-and-place-rules.md) to a service edited live.

## Context

The NWS Damage Assessment Toolkit (DAT) publishes post-event damage surveys
through one public ArcGIS FeatureServer: damage points (layer 0, 240,169
features on 2026-09-29), tornado tracks (layer 1, 12,965), and damage areas
(layer 2, 11,152), with photographs attached to the points. The roadmap had
held it back for want of an ArcGIS REST transport. `fema:nfhl`, planned, is
served the same way, so whatever reads the DAT should not know it is the DAT.

Probing the live service before writing the adapters found six things that
shape the design.

1. **A layer caps each answer at `maxRecordCount` (2000 here) and can list
   every matching object id in one answer.** All 240,169 point ids arrive in
   1.8 MB in about a second. A capped feature page says so with
   `exceededTransferLimit`, in Esri JSON and in GeoJSON alike.
2. **The service is edited live.** Its capabilities are `Query,ChangeTracking`;
   tracks for 6 May 2024 were still being added on 21 May.
   Offset pages over such a layer shift whenever a feature before them is
   added, deleted, or edited out of the window.
3. **It keeps an archive and answers `historicMoment`.** Each layer's
   `archivingInfo` says so, from `startArchivingMoment` on 25 November 2020.
   The 6 May 2024 window held 20 tracks as of 8 May, 41 as of 12 May, 55 as of
   1 June, and 58 now, and a request at a recent moment returned the live
   page byte for byte. A moment before the archive begins silently answers
   with nothing: 27 April 2011's points count 0 as of 25 November 2020 and
   1,402 a day later.
4. **The service reports its own failures as HTTP 200** with an `error` body.
5. **`queryAttachments` stops at 2000 attachments per answer and does not say
   so.** A year of 2011 points returned exactly 2000, with no flag.
6. **Dates are UTC epoch milliseconds, and a few are missing.** 41 points, 1
   track, and 254 areas have no `stormdate`. Every track has a `starttime`,
   equal to `stormdate` wherever both exist; the one track without a
   `stormdate` is a 27 April 2011 EF4 entered in June 2026. Older points often
   carry only a date, stamped at 00:00 UTC (2,650 of 2011's 5,217), and eleven
   carry the epoch itself, 1970-01-01T00:00Z, as a placeholder.

## Decision

**ArcGIS REST is a protocol module, `usdata.protocols.arcgis`.** It builds
`/query` URLs (a `where` clause, an optional WGS84 envelope, output fields,
order, `historicMoment`, and format), reads a layer's metadata, lists object
ids, reads one page of Esri JSON features, lists attachments through
`queryAttachments` or one feature's `/attachments`, and checks a downloaded
GeoJSON page. It knows no layer or field of any dataset. Every JSON answer is
refused if it holds an `error` body, whatever its status. It is not a new
`Protocol` value: the bytes arrive by plain HTTPS GET, assets are `http`, and
nothing downstream would branch on the difference, where ERDDAP's value exists
because the CSV reader does.

**Features are delivered as GeoJSON, as served.** The service's GeoJSON is
standard, carries every attribute, and was identical across repeated requests,
so a page pins. Esri JSON would need its own reader to become geometry;
GeoJSON needs none to be read with the standard library, and any geospatial
reader added later opens it. There is no bundled reader, so the entry says
`reader: null` ([ADR 0042](0042-one-open-method-per-format.md) adds a method
only for a format a bundled reader opens).

**A page is an object-id range, not an offset.** Listing asks for every
matching id, sorts them, cuts them into runs of at most the layer's
`maxRecordCount`, and makes each run one asset: the same `where` plus
`objectid >= first AND objectid <= last`, ordered by object id. ADR 0003 and
ADR 0035 paged by offset under a total order, because their services offered
nothing better. Here an edit changes only the page whose range holds it, and a
feature added later falls past every listed range rather than shifting them
all, so a relisting keeps the pages it can. A fetched page that the service
cut short, which could happen only if an edit pushed more than the limit into
a range, is refused rather than kept.

**`as_of` pins a listing to the archive.** A query that names an instant sends
it as `historicMoment` on every request, so the ids, pages, and attachments are
those of that instant and cannot drift. It is optional and records itself in
each asset's `properties`, the one fact of the request the bytes do not state
([ADR 0043](0043-asset-properties.md)). The adapter reads the archive's start
from the layer and refuses an earlier instant, where the service would answer
with nothing, and refuses a future one, which would drift until it arrived.
It is not the default: a moment chosen by listing would make every listing
differ, and the service's live state is what most queries mean.

**A window selects by storm time, inclusive at both ends, and undated features
are left out unless asked for.** Points and areas select on `stormdate`,
tracks on `starttime`, which is never empty. `include_undated` adds features
with no storm time to every window, as `include_open` does for OpenFEMA's
open incidents: including them by default would put the same rows in every
answer, and leaving them out is an omission the guide can state. Midnight and
epoch stamps are left as served; the guide says how to widen a window for
them.

**Photos are their own dataset, one asset per attachment.** They are a
different kind of file with a different cost: the 38 photos of one office's
points for one night of May 2024 are 226 MB. Listing finds the points, pages
their attributes by the same id ranges, and asks for their attachments a
hundred points at a time, asking again in halves whenever an answer reaches
the silent cap. Only JPEG and PNG attachments of the points are served; the
few files on tracks and areas are radar images, PDFs, video, and archives.
Thumbnails are kept as served: many points surveyed before 2017 carry a small copy
of each photo under the same name or a `thumb_` prefix, and no rule tells them
apart reliably (one pair is 11,475 and 12,092 bytes). The window is capped at
seven days, which bounds a listing to a few hundred requests.

## Alternatives

- **Offset paging with a count, as ADR 0035.** Simpler, and every edit before
  a page moves every page after it.
- **One whole-layer export.** `supportedExportFormats` lists GeoJSON, but an
  export is an asynchronous job, and a whole layer drifts with every edit
  anywhere.
- **`as_of` by default, at the listing's own instant.** Every page would be
  immutable, and no two listings of the same query would agree.
- **Filter on the layer's time field with the `time` parameter.** It reaches
  only the layer's declared `stormdate`, which is empty on one track that
  `starttime` holds.
- **Drop thumbnails by rule.** The smaller of two same-named files is usually
  a thumbnail, and not always; files named `thumb_` are another pattern. A
  rule would delete real photos to save a few kilobytes each.
- **A `Protocol.ARCGIS` value.** Consistent with ERDDAP, and a change to the
  shared model that nothing would read.

## Consequences

The ArcGIS helpers join the transport helpers ADR 0027 lists as the adapter
contract. `fema:nfhl` and any later ArcGIS source reuse them.

A listing costs one metadata request and one id request, plus, for photos,
one attribute request per 2000 points and one attachment request per 100.

A page listed without `as_of` still drifts when a feature inside its range is
edited, which a restore reports as a checksum mismatch. That is the service's
nature, and `as_of` is the answer the guide gives.

A window that starts at the storm's local evening misses older points stamped
with only their date at 00:00 UTC. The guides say to span whole UTC days for
surveys before 2021, when such stamps become rare.
