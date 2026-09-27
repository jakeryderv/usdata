# ACS 5-year estimates

`census:acs-5year` uses the detailed tables of the American Community Survey
5-year estimates through the
[Census Data API](https://www.census.gov/data/developers/data-sets/acs-5year.html),
checked on 2026-09-27 with a registered key. The ACS is the Census Bureau's
continuous household survey; a 5-year estimate pools five years of responses,
so it reaches every county and is the one to use for small places. The
detailed tables hold tens of thousands of variables per vintage: population,
housing, income, commuting, language, and more, each with a margin of error.

One row is one geography, a state or a county, with the variables asked for.

This product uses the Census Bureau Data API but is not endorsed or certified
by the Census Bureau.

## A key is required

Every data request carries a key. Request one at
[api.census.gov/data/key_signup.html](https://api.census.gov/data/key_signup.html)
with an organization name and an email address. The key arrives by email with
an activation link, and the service refuses it until the link is followed.

Set it in the environment:

```sh
export USDATA_CENSUS_KEY="the-key-from-the-email"
```

Any secret manager that sets environment variables works, and so does
`uv run --env-file`. A manifest never holds the key, and it appears in no
lockfile, provenance sidecar, cached file, dry-run line, or error message.
`usdata doctor` reports whether it is set without printing it. Without it,
`fetch` and `pull` stop before any request and name the variable. A locked
restore can still come from the cache, or from a configured mirror, without
asking the Census Bureau; see
[provenance and drift](../concepts/provenance-and-drift.md#restoring-from-a-mirror).

## Selecting

- **Vintage.** `-p vintage=2023` names the estimates by the last year of their
  five-year period: 2023 is 2019 through 2023. It is required, and `--start`
  and `--end` are refused, because a five-year estimate describes a period,
  not an instant ([ADR 0045](../adr/0045-acs-5year-selection.md)). The API
  lists vintages from 2009; a vintage it does not publish is refused when the
  file is fetched.
- **Variables.** `--vars NAME,B01003_001E,B01003_001M` names one to fifty API
  variables, `NAME` included, the service's limit per request. More than fifty
  is refused: split them across manifest sources. Names are upper-cased and
  repeats dropped; the columns arrive in the order given. The variables of a
  vintage are listed, without a key, at
  `https://api.census.gov/data/2023/acs/acs5/variables.json`, and one at
  `.../variables/B01003_001E.json`. An unknown name is refused when the file
  is fetched, with the service's message.
- **Place.** `--location` names one state or county; a box names no place and
  is refused.
- **Geography.** `-p geography=county` with a state returns one row per
  county in it. By default a row is the place named: the state's own row for
  a state, the county's for a county.

```sh
usdata fetch census:acs-5year --location "Osage County, OK" --vars NAME,B01003_001E,B01003_001M -p vintage=2023
usdata fetch census:acs-5year --location Oklahoma --vars NAME,B01003_001E,B25001_001E -p vintage=2023 -p geography=county
```

!!! note "Connecticut"
    Census geography replaced Connecticut's eight counties with nine planning
    regions as county equivalents in 2022, and the ACS follows its geography
    year: vintages through 2021 hold the counties (`09001` to `09015`), and
    vintages from 2022 the regions (`09110` to `09190`). A place the vintage
    does not have is refused with the ones it overlaps that it does have, so
    `Hartford County, CT` is refused for vintage 2023 and
    `Capitol Planning Region, CT` for vintage 2021. `--location Connecticut`
    with `-p geography=county` returns whichever set the vintage has. See
    [Connecticut](/reference/places.md#connecticut).

## What arrives

One JSON file per source, as the service served it: an array whose first row
names the columns and whose other rows are one geography each. The geography
columns, `state` and `county`, follow the variables asked for. Every value is
a string. The response carries no copy of the key and identical requests
return identical bytes, so, unlike AQS, nothing is rewritten before it is
pinned.

The file's name records the vintage, the place, and a digest of the variable
list, such as `acs5_2023_40-counties_f62749a38597.json`. The asset's
`properties` record the `vintage` and the `period`, such as `2019-2023`,
which the file itself does not state.

## Reading the rows

`open()` returns one row per geography with the columns as the service names
them. Estimate (`...E`) and margin-of-error (`...M`) columns are numbers,
nullable integers where every value is whole. `NAME`, the geography codes,
and annotation columns (`...EA`, `...MA`) stay text, so `"001"` keeps its
leading zeros. `attrs["usdata"]["properties"]` holds the vintage and period.

Some values are not numbers at all but negative
[annotation codes](https://www.census.gov/data/developers/data-sets/acs-1year/notes-on-acs-estimate-and-annotation-values.html),
which the reader leaves as they are because each means something different:

| Code | Meaning |
|---|---|
| `-999999999` | Too few sample cases to show the estimate or margin of error |
| `-888888888` | Not applicable or not available |
| `-666666666` | The estimate could not be computed: too few sample observations |
| `-555555555` | No margin of error: the estimate is controlled to an independent count |
| `-333333333` | The margin of error could not be computed: the median is in an open-ended interval |
| `-222222222` | The margin of error could not be computed: too few sample observations |

Total population is controlled, so every county's `B01003_001M` is
`-555555555`. Filter or mask the codes before summing or averaging a column;
request the `EA` and `MA` annotation variables when the reason matters.

## What the service does not say

- **No revision marker.** The response has no `ETag`, `Last-Modified`, or
  date. A table the Bureau reissues changes the served bytes, and a later
  restore reports that as drift.
- **An empty answer is not an error to the service.** A geography the vintage
  lacks comes back as `204` with no body; usdata refuses it rather than pin
  an empty file.
- **Vintages overlap.** The 2022 and 2023 estimates share four years of
  responses, so they are not independent, and comparing them is not a
  year-on-year change. The Census Bureau advises
  [comparing non-overlapping periods](https://www.census.gov/programs-surveys/acs/guidance/comparing-acs-data.html).
- **Dollar values are in the vintage year's dollars.** Median household
  income in vintage 2023 is inflation-adjusted to 2023, and a comparison with
  another vintage needs adjusting first.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, and
variables comes from one of these pages. A field the agency does not publish
is left empty rather than estimated.

- The service, its geographies, and the tables:
  [ACS 5-year estimates for developers](https://www.census.gov/data/developers/data-sets/acs-5year.html),
  which says the detailed tables reach down to the block group.
- Variable names, labels, and types: the API's own
  `https://api.census.gov/data/2023/acs/acs5/variables/<name>.json`.
- Annotation codes:
  [notes on ACS estimate and annotation values](https://www.census.gov/data/developers/data-sets/acs-1year/notes-on-acs-estimate-and-annotation-values.html).
- Cadence: the [ACS data releases](https://www.census.gov/programs-surveys/acs/news/data-releases.html)
  page, which dated the 2020-2024 estimates to 8 January 2026. It publishes a
  schedule rather than a latency figure, so none is given.
- Citation: no citation form was found on the developer pages, so the entry
  uses the "Agency, Product, accessed via usdata" form.
- Terms and the required notice above: the
  [API terms of service](https://www.census.gov/data/developers/about/terms-of-service.html).
- License: the data is a work of the U.S. Government.
- No window limit is declared: the adapter takes a vintage, not a window.

[Census access notes](census.md).

--8<-- "generated/catalog/census/acs-5year.md"
