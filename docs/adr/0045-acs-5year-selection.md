# 0045: ACS 5-year estimates are selected by vintage, variables, and one place, and kept as served

Status: accepted. Date: 2026-09-27. Applies
[ADR 0039](0039-credentialed-sources.md),
[ADR 0034](0034-query-keeps-the-resolved-place.md), and
[ADR 0043](0043-asset-properties.md).

## Context

`census:acs-5year` is the second source that needs a key
([issue 379](https://github.com/jakeryderv/usdata/issues/379)). The Census Data
API answers a query such as
`/data/2023/acs/acs5?get=NAME,B01003_001E&for=county:*&in=state:40` with one JSON
array of arrays: a header row, then one row per geography. The requested
variables come first and the geography columns (`state`, `county`) are appended.
Every value is a string. A vintage is the last year of a five-year period, so
2023 describes 2019 through 2023. Vintages 2009 through 2024 are listed in
`https://api.census.gov/data.json`.

Probing with a registered key on 2026-09-27 showed:

- **No echo and no variation.** The key appears in neither the body nor the
  headers, and two identical requests return identical bytes, with rows sorted
  by geography code. There is no `ETag` or `Last-Modified`.
- **Fifty variables per request, `NAME` included.** The fifty-first is refused
  with `400` and `error: 'get' is limited to 50 variables`. The geography columns
  do not count.
- **Errors take four shapes.** An unknown variable is `400` with a one-line
  plain-text message. An unknown vintage is a `404` HTML page. A missing or
  invalid key is a `302` to `missing_key.html` or `invalid_key.html`. A
  geography the vintage does not have is `204` with an empty body, not an error.
- **Connecticut changes codes at vintage 2022.** Vintage 2021 lists the eight
  old counties (`09001`–`09015`); 2022 and 2023 list the nine planning regions
  (`09110`–`09190`). Asking vintage 2021 for a region is the same empty `204`.
- **Sentinels are routine.** `B01003_001M` is `-555555555` for every Oklahoma
  county, the ACS annotation for a controlled estimate whose margin of error is
  not applicable. The ACS uses a set of such negative codes, each with its own
  meaning.

Metadata is served without a key: the vintage list, each vintage's
`variables/<name>.json` and `groups/<group>.json`, and `geography.json`.

## Decision

**Scope.** The detailed tables (`acs/acs5`) only. Subject tables, data profiles,
the 1-year survey, and the decennial census are separate datasets if a use case
asks for them.

**Vintage, not a window.** `vintage` is a required integer parameter. A query
with a time window is refused with a message that names `vintage`, and the
registry entry sets `temporal_subset: false`. A five-year estimate describes a
period, not an instant, and any rule that chose a vintage from a window (the
latest ending before it, the one containing it) would pick silently among
estimates that differ. A vintage the service does not publish is its `404`,
re-raised at fetch as a `QueryError` naming the vintage, so a new vintage needs
no release of usdata.

**Variables.** `variables` names one to fifty API variables, `NAME` included,
in any case. They are upper-cased, de-duplicated, and kept in the order given,
which is the column order of the response. More than fifty is an error that
says to split them across sources, as AQS does for parameter codes (ADR 0040),
rather than silently becoming several requests with a join nobody asked for.
Margins of error and annotation columns are ordinary variables
(`B01003_001M`, `B01003_001EA`). Listing does not check the names against the
metadata; the service's `400` is re-raised at fetch as a `QueryError` carrying
its message, and nothing is written.

**Place.** Exactly one resolved place, per ADR 0034: a state
(`for=state:SS`) or a county (`for=county:CCC&in=state:SS`). A box, or a
location without a place, is refused; `spatial_subset` stays false. Tracts and
block groups wait for an example that needs them, and would add a
`geography` parameter rather than change these two.

**Connecticut by vintage.** The place table holds both sets of codes. A
planning region asked of a vintage before 2022 is refused with the counties it
overlaps, as `Provider.refuse_planning_region` does for sources that never
changed. An old county asked of vintage 2022 or later is refused with the
planning regions it overlaps. The second rule is new; its helper lives beside
`legacy_counties` in `usdata.query`, and the base class gains no method until a
second source needs it. A state query is unaffected: it returns whichever
counties the vintage has.

**Assets.** One per request. The id is
`acs5_<vintage>_<geoid>_<hash>.json`, where the geoid is the place's two- or
five-digit code and the hash is a short digest of the variable list in order.
The href is the request without the key. `time` spans 1 January of the first
year through the end of the vintage year. `properties` records `vintage` and
`period` (for example `2019-2023`), which the bytes do not state (ADR 0043).
Listing makes no request.

**Fetch.** The key is added at send time inside `redacted_errors`
(ADR 0039). The body is written as served. There is no canonical form, because
nothing in it needs removing and identical requests already agree; the contract
checks still search the written bytes for the key. A `204` raises a
`QueryError` naming the vintage and geography, and nothing is written, since an
empty file would pin "no such place" as if it were data. The two `302`s raise
distinct credential errors, missing and invalid, before anything is written.

**Sentinels as served.** The reader types estimate and margin columns as
numbers and keeps geography codes and `NAME` as text, with leading zeros. The
negative annotation codes are left as the values they are. Each has a
[documented meaning](https://www.census.gov/data/developers/data-sets/acs-1year/notes-on-acs-estimate-and-annotation-values.html):
too few sample cases (`-999999999`, `-666666666`, `-222222222`), not applicable
(`-888888888`), a median in an open-ended interval (`-333333333`), or a
controlled estimate with no sampling error (`-555555555`). Replacing them all
with missing values would lose which one applied. The guide lists the codes, and says to request the `EA`/`MA`
annotation columns when the distinction matters.

## Consequences

A comparison across vintages is one source per vintage, and the lockfile pins
each separately. Two vintages that overlap in years are not independent
samples, and the guide says so; choosing between them is analysis.

A mistyped variable is found at fetch, not by a dry run. Checking it at listing
would mean one metadata request per variable, or a multi-megabyte variables
file per vintage, for an error the service already reports clearly.

When the Census Bureau reissues a table, the served bytes change and surface
as drift, which `pull --update` accepts.

ADR 0039 needs no amendment for this source as far as probing shows. The
credential is one variable, `USDATA_CENSUS_KEY`, sent as a query parameter, and
the rules written for AQS's pair of variables cover it. That is the question
this dataset was chosen to answer, and the contract checks settle it when the
adapter lands; a failure there amends ADR 0039 rather than bending the adapter.
