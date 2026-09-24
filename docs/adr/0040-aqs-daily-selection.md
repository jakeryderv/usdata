# 0040: AQS daily summaries are selected by pollutant codes and one place, a year per request

Status: accepted. Date: 2026-09-23. Applies
[ADR 0039](0039-credentialed-sources.md) and
[ADR 0034](0034-query-keeps-the-resolved-place.md).

## Context

`epa:aqs-daily` is the first source that needs a key. The AQS Data API's
`dailyData` service returns one JSON document per request: a `Header` and a
`Data` list with one element per monitor, local day, and pollutant standard. A
request names parameter codes and a place in one of five ways: `bySite`,
`byCounty`, `byState`, `byBox`, or `byCBSA`. The
[documentation](https://aqs.epa.gov/aqsweb/documents/data_api.html) sets three
limits: at most five parameter codes per request, `bdate` and `edate` in the
same calendar year, and requests sent one at a time, at most ten a minute, with
a pause between them. Accounts that ignore the limits may be disabled.

Probing with a registered key on 2026-09-23 added more:

- **Responses are slow.** Ten days of PM2.5 for Queens County took about two
  minutes to return 238 rows (276 KB).
- **Rows repeat a monitor-day.** The same monitor and day appear once per sample
  duration, once per pollutant standard (eight PM2.5 standards in that
  response), and separately for `Events Included` and
  `Concurred Events Excluded` where a day was flagged as an exceptional event.
  Ten of the 228 identity tuples without `event_type` repeated.
- **An empty selection is not an error.** It returns HTTP 200 with the header
  status `No data matched your selection` and no rows, and so does a parameter
  code that does not exist (`99999`).
- **The echo and the ordering** described in ADR 0039: the header holds the
  request URL with the key, and the row order and `request_time` change between
  identical requests.

## Decision

**Parameters.** `parameters` names one to five AQS parameter codes, as integers
or text, so an unquoted `88101` in a manifest works. More than five is an error
that says to split them across sources, rather than silently becoming several
requests. `variables` is refused: the columns are fixed.

**Place.** Exactly one of three:

- `sites`: AQS site ids `SS-CCC-NNNN`, one `bySite` request each.
- A `location` naming a county or state: `byCounty` or `byState`, which select
  it exactly. This applies ADR 0034, since a county's bounding box takes in
  monitors in its neighbours.
- A bare `bbox`, or `lat`/`lon` with a radius: `byBox`.

`sites` together with a location or box is an error. `byCBSA` is left out;
a county, state, or box covers the same ground, and a metro-area code can be
added later without changing these three.

**Time.** Both bounds are required. The UTC calendar dates of the bounds select
AQS `date_local` days, inclusive, as the other daily station sources do. A
local day is not a UTC interval, and the reader leaves it as a naive date. Each
calendar year the window touches becomes its own asset, because the service
refuses a request that crosses one.

**Assets.** One per selection and year. The id is
`aqs-daily_<selection>_<codes>_<bdate>_<edate>.json`, where the selection is
`site-SS-CCC-NNNN`, `county-SSCCC`, `state-SS`, or `box-<hash>` of the box's
bounds. The href is the request without credentials. Listing makes no request,
so a dry run needs a key only because the adapter cannot be built without one.

**Fetch.** Following ADR 0039: credentials added at send time inside
`redacted_errors`, and the canonical form written. The header keeps every field
but `url` and `request_time`. Rows are sorted by site, parameter, POC, local
date, duration, standard, method, and event type, with the serialized row as the
final tiebreak. The JSON is written with sorted keys and compact separators. A
header status other than `Success` or `No data matched your selection` raises
`AqsError`, and nothing is written. An empty selection is written as a file
with no rows, so a pin records that nothing matched. The service answers an
unknown parameter code the same way, so a mistyped code is an empty file rather
than an error; telling the two apart would cost a second request, and the guide
says to check the code instead.

**Pacing.** Every request from the module waits until at least six seconds
have passed since the previous one started, across adapter instances in the
process: a pause, and at most ten a minute. The read timeout is ten minutes.

**Rows as delivered.** No row is filtered or merged. Choosing a standard, a
duration, or whether exceptional events count is analysis, and the guide
explains the columns that decide it.

## Consequences

A state-year of a common pollutant is one slow request and a large file, and a
ten-year query for three sites is thirty requests, at least three minutes of
pacing on top of the service's own time. The guide says so, and the dry run
shows the request count before anything is sent.

A pin covers a whole selection-year. When an agency revises one day, the
year's canonical bytes change, `date_of_last_change` shows which rows moved,
and `pull --update` accepts the new bytes.

Pacing is per process. Two processes sharing a key can together exceed EPA's
limits, and nothing here prevents it. A retry after a 5xx or 429 follows the
shared transport policy, which waits well under six seconds; that is rare
enough to leave, and a 429 with `Retry-After` is honoured.
