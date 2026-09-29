# NWS damage survey photos

`noaa:nws-damage-photos`, available since v0.34, serves the photographs NWS
surveyors attach to damage points in the
[Damage Assessment Toolkit](https://apps.dat.noaa.gov/StormDamage/DamageViewer/),
from the same public ArcGIS feature service as
[`noaa:nws-damage-surveys`](noaa-nws-damage-surveys.md), checked on 2026-09-29.
Each photo is one asset: the JPEG or PNG exactly as the service stores it.

- Both timestamps are required, in UTC, and may span at most **7 days**. The
  window selects the damage points whose `stormdate` falls in it, inclusive at
  both ends; the storm-time caveats of the
  [surveys guide](noaa-nws-damage-surveys.md#storm-times) apply unchanged, and
  matter more here, because older photographed points often carry only their
  date at 00:00 UTC.
- A `bbox` or `location` selects points inside it, on the server.
- `-p office=`, `-p efscale=`, `-p include_undated=true`, and `-p as_of=`
  select points exactly as they do for the surveys' `points` layer.
- `variables` is rejected, and so is free text.

```sh
usdata fetch noaa:nws-damage-photos --start 2024-05-06T12:00Z --end 2024-05-07T12:00Z \
  -p office=TSA -p efscale=EF4 --dry-run
usdata fetch noaa:nws-damage-photos --start 2011-04-27 --end 2011-04-28 \
  --bbox -87.75,34.30,-87.65,34.40 -p efscale=EF5
```

## Listing, and what it costs

Listing makes three kinds of request: the point ids matching the query, the
points' storm time, rating, and location, 2000 points at a time, and their
attachments through `queryAttachments`, 100 points at a time. That service
stops at 2000 attachments per answer without saying so, so an answer that
reaches the limit is asked again in halves. The 1,465 photos on 735 points
from 27 and 28 April 2011 listed in 23 seconds.

Photos are large. The 38 photos from Tulsa's points on the night of 6 May 2024
total 226 MB, about 6 MB each; those 1,465 from April 2011 total 358 MB.
Every asset carries the size the service lists, so `--dry-run` says what a
fetch would move before anything is downloaded, and a fetched file of any
other size is refused and removed.

## What each asset says

- `id`: `nws_damage_photo_<point objectid>_<attachment id>.jpg` or `.png`.
  Attachment ids are unique across the layer and do not change.
- `href`: `.../FeatureServer/0/<point objectid>/attachments/<attachment id>`.
- `media_type` and `size`, from the attachment listing.
- `time`: the point's storm time as an instant, or none for an undated point.
- `bbox`: the point's position, a box of no extent.
- `properties`: `point_objectid` and `point_globalid`, which join a photo to
  its point in `noaa:nws-damage-surveys` with `layer=points`; `efscale`, the
  point's rating when it has one; and `name`, the file name the photo was
  uploaded under, which often holds the camera's own name and time. The JPEG
  states none of these, and the EXIF position is present on some photos only.

## Thumbnails

Many points surveyed before 2017 hold a small copy of each photo beside it,
and both are listed, as the service holds them. Two patterns were seen:

- The same file name twice. Point 25520, at Phil Campbell, Alabama, holds
  `20110501_160432_IMG_0342.JPG` as attachment 15668 (167,209 bytes) and again
  as 20831 (7,015 bytes). In 2012, 1,207 of the 2,590 photos on points were
  such pairs; the smaller copy was at most 22.8 KB, and the two checked were
  192 pixels wide. The copies' attachment ids run in one block, 20,831 to
  about 25,700, as if made in one batch.
- A `thumb_` prefix, as `thumb_3svr7MzL_1370093531000.jpg` (54,580 bytes)
  beside its 1,038,213-byte original.

The Phil Campbell thumbnails in the walkthrough carry no EXIF, where their
photos do.

The adapter does not drop either. Neither rule is reliable: point 2016826
holds two same-named copies of 11,475 and 12,092 bytes, which a size rule
would split into a photo and its thumbnail. Use `size` to tell them apart; the
walkthrough drops the smaller of each same-named pair.

## What is not served

Files attached to tracks (177) and damage areas (35) are not photos of damage
points: PNG radar images, PDF survey summaries, a panorama PDF, video, and one
zip archive. They are left out, as is any attachment of a point whose type is
not JPEG or PNG; none was seen in the probes.

Some photos come from the public or partners rather than NWS staff. The NWS
disclaimer says "Third-party information and imagery are used under license by
the individual third-party provider", and nothing in the listing says which
photos those are.

## Probes

Checked on 2026-09-29.

```sh
B='https://services.dat.noaa.gov/arcgis/rest/services/nws_damageassessmenttoolkit/DamageViewer/FeatureServer'
curl -G "$B/0/queryAttachments" -d objectIds=3989962,3989963 -d f=json     # two JPEGs, 1.9 and 3.5 MB
curl -G "$B/0/queryAttachments" --data-urlencode "definitionExpression=stormdate >= TIMESTAMP '2011-01-01 00:00:00' AND stormdate < TIMESTAMP '2012-01-01 00:00:00'" \
  -d f=json                                                                    # exactly 2000, no flag
curl -o thumb.jpg "$B/0/28647/attachments/21730"                            # 5,228 bytes, 192 x 144
curl -o photo.jpg "$B/0/28647/attachments/16567"                            # 577,848 bytes, 2048 x 1536
curl -G "$B/1/queryAttachments" --data-urlencode 'definitionExpression=1=1' -d f=json   # 177: PNG, JPEG, PDF, video, zip
```

## Metadata sources

- What the DAT is and how data reach the public service: NWS
  [Service Change Notice 22-84](https://www.weather.gov/media/notification/pdf2/scn22-84_damage_assessment_toolkit.pdf).
- Attachment fields, types, sizes, and the silent cap: the
  [feature service](https://services.dat.noaa.gov/arcgis/rest/services/nws_damageassessmenttoolkit/DamageViewer/FeatureServer),
  layer 0's `attachmentProperties` and `queryAttachments`, probed as above.
- Temporal extent: the earliest photographed point with a real storm time is
  a 1974 Super Outbreak reconstruction, 1974-04-03; four points dated with the
  1970-01-01 placeholder also carry photos.
- Terms and license: the NWS [disclaimer](https://www.weather.gov/disclaimer),
  for NWS information and for third-party imagery.
- Citation: the DAT publishes no citation form.
- Latency and update frequency: as for the surveys; photos arrive with their
  points.
- The 7-day window is the adapter's own bound on how many requests one listing
  makes.

[NOAA access notes](noaa.md).

--8<-- "generated/catalog/noaa/nws-damage-photos.md"
