<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

## Reference

`fema:disaster-declarations` · **Released** · Included since usdata 0.21. FEMA Disaster Declarations Summaries.

### At a glance

- Files: CSV
- Selection: Declarations whose incident period overlaps an inclusive UTC window, for a named state or county; a county also returns its state's statewide designations
- Required inputs: Both dates; optionally a state or county location, or state or fips, and type filters
- Open locally: `usdata[pandas]` · [Reader guide](../reference/readers.md)
- On usdata.dev: [Federal disaster declarations by county](https://usdata.dev/datasets/fema/disaster-declarations/)
- Studies: [Which Oklahoma counties hit by a tornado on 6 May 2024 were under a federal disaster declaration?](https://usdata.dev/studies/disaster-declarations/)

### Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `declaration_type` | Declaration type(s): DR (major disaster), EM (emergency), FM (fire). |
| `fips` | Five-digit FIPS code of one county, such as 40113; also returns its state's Statewide designations. |
| `incident_type` | Incident type(s) as FEMA writes them, such as Tornado or Severe Storm. |
| `include_open` | Also return incidents with no end date, most of them old fire declarations that were never closed; false by default. |
| `state` | Two-letter postal code of one state or territory, such as OK. |

### Variables

| Variable | Units | Meaning |
|---|---|---|
| `femaDeclarationString` | — | Declaration type, disaster number, and state code joined, such as DR-4393-NC |
| `disasterNumber` | — | Sequentially assigned number designating the declared event |
| `state` | — | Two-letter code of the state, district, or territory |
| `declarationType` | — | DR major disaster, EM emergency, or FM fire management |
| `declarationDate` | ISO 8601 UTC | Date the disaster was declared |
| `fyDeclared` | — | Fiscal year in which the disaster was declared |
| `incidentType` | — | Primary type of incident, such as Fire or Flood |
| `declarationTitle` | — | Title for the disaster |
| `ihProgramDeclared` | — | Whether the Individuals and Households program was declared |
| `iaProgramDeclared` | — | Whether the Individual Assistance program was declared |
| `paProgramDeclared` | — | Whether the Public Assistance program was declared |
| `hmProgramDeclared` | — | Whether the Hazard Mitigation program was declared |
| `incidentBeginDate` | ISO 8601 UTC | Date the incident itself began |
| `incidentEndDate` | ISO 8601 UTC | Date the incident itself ended; empty while open |
| `disasterCloseoutDate` | ISO 8601 UTC | Date all financial transactions for all programs are completed |
| `tribalRequest` | — | Whether a Tribal Nation submitted the request directly to the President |
| `fipsStateCode` | — | Two-digit FIPS code of the state, district, or territory |
| `fipsCountyCode` | — | Three-digit FIPS code of the county; 000 for a statewide or tribal designation |
| `placeCode` | — | FEMA's own location code, 99 plus the county code, covering areas with no FIPS county code |
| `designatedArea` | — | Name of the geographic area included in the declaration |
| `declarationRequestNumber` | — | Number assigned to the declaration request |
| `declarationRequestDate` | ISO 8601 UTC | Date the declaration request was made |
| `lastIAFilingDate` | ISO 8601 UTC | Last date Individual Assistance requests can be filed; after 1998 only |
| `incidentId` | — | Identifier of the incident, which may or may not become a declared disaster |
| `region` | — | FEMA region, 1 to 10, where the disaster occurred |
| `designatedIncidentTypes` | — | Comma-separated codes of every incident type designated for the disaster |
| `lastRefresh` | ISO 8601 UTC | When the record was last updated in the API data store |
| `hash` | — | MD5 hash of the record's fields and values |
| `id` | — | Unique id assigned to the record |

### Catalog facts

- Availability: since 0.21
- Domain: Natural hazards
- Spatial resolution: One row per designated area: a county or county equivalent, a tribal area, or a whole state
- Temporal resolution: Calendar dates for the declaration and for the start and end of the incident
- Updates: Every twenty minutes (R/PT20M); a record's lastRefresh moves only when it changes
- Terms of use: <https://www.fema.gov/about/openfema/terms-conditions>
- Citation: Federal Emergency Management Agency (FEMA), OpenFEMA Dataset: Disaster Declarations Summaries - v2. Retrieved from https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries on [date, time]. This product uses the Federal Emergency Management Agency's OpenFEMA API, but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses derived from these data after the data have been retrieved from the Agency's website(s).
- Catalog date range: 1953-01-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://www.fema.gov/openfema-data-page/disaster-declarations-summaries-v2)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.fema.declarations:DisasterDeclarations`
