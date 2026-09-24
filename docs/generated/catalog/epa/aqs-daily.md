# Daily air pollutant summaries from regulatory monitors

<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

`epa:aqs-daily` · **Released** · Included since usdata 0.26.

Air Quality System Daily Summaries.

## At a glance

- Files: JSON
- Selection: Local days within inclusive UTC calendar dates for one to five pollutants; one file per year
- Required inputs: Both dates; one to five parameter codes; site ids, a state or county, or a box
- Credentials: `USDATA_AQS_EMAIL`, `USDATA_AQS_KEY` in the environment ([request a key](https://aqs.epa.gov/aqsweb/documents/data_api.html#signup))
- Open locally: `usdata[pandas]` · [Reader guide](../../../reference/readers.md)
- On usdata.dev: [Daily air pollutant summaries from regulatory monitors](https://usdata.dev/datasets/epa/aqs-daily/), with a walkthrough
- Studies: [How far above the daily PM2.5 standard did Canadian wildfire smoke push New York City's air in June 2023?](https://usdata.dev/studies/wildfire-smoke/)

## Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `parameters` | Required AQS parameter code(s), one to five, such as 88101 (PM2.5) or 44201 (ozone). |
| `sites` | AQS site id(s) as state-county-site, such as 36-081-0124; or use a location. |

## Variables

| Variable | Units | Meaning |
|---|---|---|
| `state_code` | — | FIPS code of the state the monitor is in; 80 for Mexico, CC for Canada at border sites |
| `county_code` | — | FIPS code of the county, parish, or independent city within the state |
| `site_number` | — | Four-digit site number, unique within the county |
| `parameter_code` | — | AQS code of the parameter measured |
| `poc` | — | Parameter occurrence code distinguishing instruments measuring the same parameter at one site |
| `latitude` | degrees_north | Site latitude, WGS84 |
| `longitude` | degrees_east | Site longitude, WGS84 |
| `datum` | — | Datum of the coordinates, always WGS84 |
| `parameter` | — | Name of the parameter measured |
| `sample_duration_code` | — | Code of the sample duration |
| `sample_duration` | — | Averaging period: observed, such as 1 HOUR or 24 HOUR, or calculated, such as 24-HR BLK AVG |
| `pollutant_standard` | — | National ambient air quality standard the row's statistics are calculated for; empty for none |
| `date_local` | — | Day the sample was taken, in local standard time |
| `units_of_measure` | — | Units of every statistic on the row |
| `event_type` | — | Whether exceptional-event data are included: No Events, Events Included, Events Excluded, or Concurred Events Excluded |
| `observation_count` | — | Number of observations in the averaging period |
| `observation_percent` | percent | Share of scheduled values for the day that were reported |
| `validity_indicator` | — | Y where the value meets all completeness criteria |
| `arithmetic_mean` | — | Mean of the day's values, in units_of_measure |
| `first_max_value` | — | Highest value at the row's duration or standard, in units_of_measure |
| `first_max_hour` | — | Hour of the day, 24-hour local standard time, of the highest value |
| `aqi` | — | Air Quality Index for the day, where the pollutant has one |
| `method_code` | — | Three-digit measurement method code, unique within a parameter |
| `method` | — | Collection and analysis method |
| `local_site_name` | — | Site name in the operating agency's own nomenclature |
| `site_address` | — | Approximate street address of the site |
| `county` | — | Name of the county the site is in |
| `state` | — | Name of the state the site is in |
| `city` | — | Incorporated city the site is in, if any |
| `cbsa_code` | — | Code of the core-based statistical (metropolitan) area |
| `cbsa` | — | Name of the core-based statistical (metropolitan) area |
| `date_of_last_change` | — | Date the underlying data were last changed in AQS |

## Usage and limitations

[Usage guide](../../../providers/epa-aqs-daily.md).

## Catalog reference

- Availability: since 0.26
- Domain: Air quality
- Spatial resolution: Regulatory monitoring sites operated by state, local, and tribal agencies
- Temporal resolution: Daily summaries of each monitor's samples, one row per pollutant standard
- Updates: As monitoring agencies submit each quarter (40 CFR 58.16) and certify the previous year by May 1 (40 CFR 58.15); submitted values can be revised later
- Latency: Agencies must submit each calendar quarter's data within 90 days after it ends (40 CFR 58.16)
- Terms of use: <https://aqs.epa.gov/aqsweb/documents/data_api.html#terms>
- Citation: U.S. Environmental Protection Agency, Air Quality System (AQS) daily summary data, AQS Data API, accessed via usdata
- Coverage: not specified in the catalog
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://aqs.epa.gov/aqsweb/documents/data_api.html#daily)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.epa.aqs:AqsDaily`

[All EPA datasets](../epa.md).
