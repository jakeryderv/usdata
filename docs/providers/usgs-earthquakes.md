# Earthquake events

`usgs:earthquakes` uses the [FDSN event web service](https://earthquake.usgs.gov/fdsnws/event/1/)
in front of the [ANSS Comprehensive Catalog](https://earthquake.usgs.gov/data/comcat/),
at `https://earthquake.usgs.gov/fdsnws/event/1/query`. Service version 2.7.0
was checked on 2026-09-16.

- Both timestamps are required and inclusive, in UTC. A location, bbox, or
  point selects a bounding box; without one the query is global, which is
  where the 20,000-event cap matters.
- `-p min_magnitude=2.5` and `-p max_magnitude=` bound the magnitude, on
  whatever scale each event's `magType` names. `-p min_depth=` and
  `-p max_depth=` bound the hypocenter depth in kilometers, from -100 to 1000
  as the service allows. A lower bound above its upper bound is rejected
  before any request.
- `variables` is rejected: the CSV columns are fixed, and rows are filtered
  locally. Free text is rejected as everywhere.
- Listing calls the service's `count` method with the same filters, then
  makes one asset per page of at most 20,000 events, ordered by time
  ascending with `limit` and a one-based `offset`, so page membership is
  stable for a given catalog state. Zero matching events is an empty listing;
  a manifest source then needs `allow_empty: true`.
- Each asset is the service's CSV page: `time`, `latitude`, `longitude`,
  `depth`, `mag`, `magType`, `nst`, `gap`, `dmin`, `rms`, `net`, `id`,
  `updated`, `place`, `type`, `horizontalError`, `depthError`, `magError`,
  `magNst`, `status`, `locationSource`, `magSource`. `status` is `automatic`
  until a network reviews the event.
- Sizes are not known before download; `--dry-run` reports them as unknown.
- Access was verified without credentials. The service documents no rate
  limit; keep queries bounded rather than paging the world.

Events are revised after publication: magnitudes and locations move as
networks review them, and `updated` records when. A pinned page therefore
changes bytes when any event in it is revised, which a locked restore reports
as drift.

--8<-- "_snippets/upstream-revisions.md"

Probes used to verify the endpoint and its limits:

```sh
curl 'https://earthquake.usgs.gov/fdsnws/event/1/count?starttime=2024-05-06T00:00:00&endtime=2024-05-07T23:59:59&minlatitude=33.6&maxlatitude=37.0&minlongitude=-103.0&maxlongitude=-94.4'
curl 'https://earthquake.usgs.gov/fdsnws/event/1/query?format=csv&orderby=time-asc&limit=3&offset=1&starttime=2024-05-06T00:00:00&endtime=2024-05-07T23:59:59&minlatitude=33.6&maxlatitude=37.0&minlongitude=-103.0&maxlongitude=-94.4'
curl 'https://earthquake.usgs.gov/fdsnws/event/1/query?format=csv&starttime=2020-01-01&endtime=2024-01-01'   # 400: exceeds search limit of 20000
```

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Parameters, ranges, the 20,000-event cap, and the CSV columns: the
  [FDSN event service documentation](https://earthquake.usgs.gov/fdsnws/event/1/).
- Resolution and updates: the [ComCat documentation](https://earthquake.usgs.gov/data/comcat/),
  which describes automatic postings from contributing networks superseded by
  reviewed versions, and event times and locations as the networks report them.
- Citation: the ComCat page's recommended form, doi:10.5066/F7MS3QZH.
- Terms: the [USGS copyrights and credits
  page](https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits),
  which places USGS-produced data in the public domain and asks for credit.
- Latency is empty: the documentation states no figure for how quickly an
  event appears after it occurs.

[USGS access notes](usgs.md).

--8<-- "generated/catalog/usgs/earthquakes.md"
