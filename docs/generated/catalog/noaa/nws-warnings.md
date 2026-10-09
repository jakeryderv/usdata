<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

## Reference

`noaa:nws-warnings` · **Source only** · Install from [source](../install.md#source-installation) to use this dataset. NWS Watch, Warning, and Advisory Geometries.

### At a glance

- Files: zipped shapefile and CSV (no reader)
- Selection: Events starting inside an inclusive UTC window, one zip per UTC month; optionally one state or offices, event types, and polygon options
- Required inputs: Both timestamps; optionally a state location or wfo, events such as TO.W, storm_based, and followups
- Open locally: Local files; no bundled reader for this format
- On usdata.dev: [NWS watch, warning, and advisory polygons and areas](https://usdata.dev/datasets/noaa/nws-warnings/), with a walkthrough

### Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `events` | VTEC phenomena and significance pairs such as TO.W, SV.W, or TO.A; every watch, warning, and advisory by default. |
| `followups` | Add the polygons of follow-up statements issued after a warning, each its own row; only the issuance polygon by default. |
| `storm_based` | Keep only storm-based warning polygons (GTYPE P), dropping county and zone rows; false by default. |
| `wfo` | Issuing office code(s) such as OUN or TSA, in place of a state location; every office by default. |

### Variables

| Variable | Units | Meaning |
|---|---|---|
| `WFO` | — | Issuing office, the four-letter id without its leading K or P |
| `ISSUED` | UTC, YYYYMMDDHHMM | Event start as last updated; the window's field |
| `EXPIRED` | UTC, YYYYMMDDHHMM | Event end as last updated |
| `INIT_ISS` | UTC, YYYYMMDDHHMM | Time of the text product that started the event; never updated |
| `INIT_EXP` | UTC, YYYYMMDDHHMM | Event end as first issued; never updated |
| `PHENOM` | — | Two-letter VTEC phenomena, such as TO or SV |
| `GTYPE` | — | P for a storm-based polygon, C for a county, parish, or zone |
| `SIG` | — | One-letter VTEC significance, such as W warning, A watch, Y advisory |
| `ETN` | — | VTEC event tracking number |
| `STATUS` | — | VTEC status of the event's latest update, such as NEW, CON, CAN, EXP, UPG |
| `NWS_UGC` | — | UGC code of a county or zone row; empty on polygons |
| `AREA_KM2` | km2 | Area IEM computed in an Albers projection |
| `UPDATED` | UTC, YYYYMMDDHHMM | When NWS last updated the event |
| `HV_NWSLI` | — | Hydrologic VTEC: forecast point's NWS location id |
| `HV_SEV` | — | Hydrologic VTEC: flood severity at issuance |
| `HV_CAUSE` | — | Hydrologic VTEC: cause of the flood |
| `HV_REC` | — | Hydrologic VTEC: whether a record crest was expected at issuance |
| `EMERGENC` | — | Whether IEM's unofficial logic marks the event an emergency at any point |
| `POLY_BEG` | UTC, YYYYMMDDHHMM | Polygon rows: when the polygon becomes valid |
| `POLY_END` | UTC, YYYYMMDDHHMM | Polygon rows: when the polygon expires |
| `WINDTAG` | mph | Polygon rows: impact-based wind gust tag |
| `HAILTAG` | inches | Polygon rows: impact-based hail size tag |
| `TORNTAG` | — | Polygon rows: impact-based tornado tag, such as RADAR INDICATED or OBSERVED |
| `DAMAGTAG` | — | Polygon rows: impact-based damage threat tag, such as CONSIDERABLE |
| `PROD_ID` | — | IEM id of the issuing text product |
| `FCSTER` | — | Product signature, often the forecaster |
| `VTEC_YR` | — | Year the event's tracking number belongs to |

### Catalog facts

- Availability: Source only · intended for 0.35
- Domain: Severe weather
- Spatial resolution: A storm-based warning polygon, or one county, parish, or forecast zone outline, per row
- Temporal resolution: Issue, expiry, and polygon times to the minute
- Updates: Not stated by IEM, which processes the live NWS product stream; rows change as later products update an event
- Terms of use: <https://mesonet.agron.iastate.edu/disclaimer.php>
- Citation: National Weather Service watch, warning, and advisory products, as archived and served by the Iowa Environmental Mesonet of Iowa State University, accessed via usdata
- Catalog date range: 1986-01-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://mesonet.agron.iastate.edu/request/gis/watchwarn.phtml)
- License: Public domain (NWS products; IEM materials are public domain, attribution appreciated)
- Transport: `http`
- Adapter: `usdata.providers.noaa.nws_warnings:NwsWarnings`
