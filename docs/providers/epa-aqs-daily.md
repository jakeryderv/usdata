# AQS daily summaries

`epa:aqs-daily` uses the `dailyData` service of the
[AQS Data API](https://aqs.epa.gov/aqsweb/documents/data_api.html#daily), checked
on 2026-09-23 with a registered key. AQS is EPA's archive of regulatory air
monitoring: state, local, and tribal agencies submit, validate, and certify the
data, so it is the checked historical record, not a live feed. For today's
preliminary readings use AirNow, which is a different source.

One row is one monitor's summary for one local calendar day under one pollutant
standard: the mean and maximum of the day's samples, the hour of the maximum,
the AQI where the standard defines one, how complete the day was, and the
site's name, address, coordinates, county, and metro area.

## A key is required

Every request carries an email address and a key. Register once by opening
`https://aqs.epa.gov/data/api/signup?email=you@example.com` with your own
address; EPA emails the key from `aqsdatamart@epa.gov`. Opening the same link
again issues a new key to the same address. There is no way to delete the
account yourself.

Set both variables in the environment:

```sh
export USDATA_AQS_EMAIL="you@example.com"
export USDATA_AQS_KEY="the-key-from-the-email"
```

Any secret manager that sets environment variables works, and so does
`uv run --env-file`. A manifest never holds a key, and no key appears in a
lockfile, provenance sidecar, cached file, dry-run line, or error message.
`usdata doctor` reports whether both are set without printing them. Without
them, `fetch` and `pull` stop before any request and name the variables. A
locked restore can still come from the cache, or from a configured mirror,
without asking EPA; see
[provenance and drift](../concepts/provenance-and-drift.md#restoring-from-a-mirror).

## Selecting

- **Pollutants.** `-p parameters=88101` names one to five AQS parameter codes,
  comma-separated. 88101 is PM2.5 (local conditions), 44201 ozone, 42401 SO2,
  42602 NO2, and 42101 CO; the full list comes from the service's
  `list/parametersByClass` endpoint. More than five is refused: split them
  across manifest sources.
- **Place**, exactly one of:
    - `--location "Queens County, NY"` or `--location "New York"`: the
      county or state exactly, through `byCounty` or `byState`. A county's
      bounding box would take in monitors in its neighbours
      ([ADR 0034](../adr/0034-query-keeps-the-resolved-place.md)).
    - `-p sites=36-081-0124`: AQS site ids, state-county-site, one request each.
    - `--bbox` or `--lat`/`--lon`: the monitors inside the box, through `byBox`.
- **Dates.** Both are required. Their UTC calendar dates select AQS
  `date_local` days, inclusive. `date_local` is a day in the monitor's local
  standard time, not a UTC interval, and the reader leaves it as a naive date.
- **Years.** The service refuses a request that spans two calendar years, so
  each year the window touches is its own request and its own file.
- `variables` is refused: the columns are fixed. Free text is refused as
  everywhere.

```sh
usdata fetch epa:aqs-daily --start 2023-06-01 --end 2023-06-15 --location "Queens County, NY" -p parameters=88101
usdata fetch epa:aqs-daily --start 2023-01-01 --end 2023-12-31 -p sites=36-081-0124 -p parameters=88101,44201
```

--8<-- "_snippets/connecticut-counties.md"

EPA's site list (`aqs_sites.zip` from the AirData downloads) gave every open
Connecticut monitor a county code from `001` to `015` in September 2026.

## What arrives

A JSON file per selection and year, named
`aqs-daily_<selection>_<codes>_<first day>_<last day>.json`. It is not the bytes
as sent. The service's header echoes the whole request, key included, and its
`request_time` and the order of the rows change between identical requests. A
checksum could not pin that, so the adapter writes a canonical form: the header
without `url` and `request_time`, the rows sorted by site, parameter, POC,
local date, duration, standard, method, and event type, and the JSON with
sorted keys. Each provenance sidecar records this step under
`transformations` ([ADR 0039](../adr/0039-credentialed-sources.md)).

`item.open()` returns a pandas DataFrame with one row per element of `Data`,
the columns named as the service names them. `date_local` and
`date_of_last_change` are parsed as naive dates, identifiers such as
`state_code`, `county_code`, and `site_number` stay text, and the header is in
`frame.attrs["usdata"]["header"]`.

## Reading the rows

Several rows can describe one monitor on one day. Pick the ones a question
needs before averaging or counting:

- **`pollutant_standard`.** A PM2.5 day appears once per standard it is
  compared with (the 1997, 2006, 2012, and 2024 standards, 24-hour and annual),
  eight rows in the Queens probe, and once with no standard for the hourly
  series. Filter to one, such as `PM25 24-hour 2024`.
- **`sample_duration`.** Continuous monitors report `1 HOUR` samples, summarized
  again as `24-HR BLK AVG`; filter-based samplers report `24 HOUR`.
- **`event_type`.** A day an agency flagged as an exceptional event, such as
  wildfire smoke, appears as `Events Included` and again as
  `Concurred Events Excluded` (or `Events Excluded`). Keep `No Events` plus
  `Events Included` to see what was measured; the excluded rows are what the
  regulatory design value uses.
- **`poc`.** Parameter occurrence code: more than one instrument can measure
  the same pollutant at one site.
- **`validity_indicator`** and **`observation_percent`** say whether the day
  met completeness criteria.

## What the service does not say

- **A mistyped code looks like no data.** An unknown parameter code, such as
  `99999`, returns the same `No data matched your selection` as a valid code
  with no monitors in the place. Both are written as a file with no rows.
  Check the code if a query comes back empty.
- **It is slow.** Ten days of PM2.5 for one county took about two minutes. A
  state-year of a common pollutant takes much longer and can be tens of
  megabytes. The read timeout is ten minutes.
- **It limits callers.** EPA asks for one request at a time, at most ten a
  minute, and a pause between them, and may disable an account that ignores
  this. The adapter waits until six seconds have passed since the previous
  request started, across every adapter in the process, and a retry after a
  429, a 5xx, or a timeout waits the same way. Two processes sharing a key are
  not coordinated.
- **Values are revised.** Agencies can change submitted data, and each row
  carries `date_of_last_change`. A revised day changes its year's file, which
  a locked restore reports as drift; `pull --update` accepts it.
- **Refusals.** A request the service refuses answers with a `Failed` header
  and a reason, usually with a 4xx status. usdata raises `AqsError`, a
  `QueryError` (CLI exit 2), with that reason and without the key. An error
  without that header, such as a maintenance page, or a success that is not
  the expected JSON, is an upstream failure: an httpx error (CLI exit 4),
  also without the key.
- Sizes are not known before download; `--dry-run` lists the requests, and
  needs the key set only because the adapter cannot be built without it.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- The services, filters, limits, signup, and output format: the
  [AQS Data API documentation](https://aqs.epa.gov/aqsweb/documents/data_api.html),
  including its [request limits and terms of service](https://aqs.epa.gov/aqsweb/documents/data_api.html#terms).
- Variable descriptions: the service's own field list, from
  `metaData/fieldsByService?service=dailyData`.
- Latency and cadence: agencies must submit each calendar quarter's data
  within 90 days after it ends
  ([40 CFR 58.16](https://www.ecfr.gov/current/title-40/part-58/section-58.16)),
  and certify the previous year by May 1
  ([40 CFR 58.15](https://www.ecfr.gov/current/title-40/part-58/section-58.15)).
- Citation: EPA's AirData FAQ has a question on citing its data whose answer did
  not load when checked, so the entry uses the "Agency, Product, accessed via
  usdata" form.
- License: the data is a work of the U.S. Government.
- No window limit is declared: the adapter splits a window by year and enforces
  no longest one.

[EPA access notes](epa.md).

--8<-- "generated/catalog/epa/aqs-daily.md"
