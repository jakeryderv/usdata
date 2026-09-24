<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

## Reference

`noaa:nws-vtec-events` · **Released** · Included since usdata 0.22. NWS Watch, Warning, and Advisory Events by County.

### At a glance

- Files: CSV
- Selection: Events issued for one county or UGC inside an inclusive UTC window; optionally one event type
- Required inputs: Both timestamps; a county location or a ugc; optionally phenomena with significance
- Open locally: `usdata[pandas]` · [Reader guide](../reference/readers.md)
- On usdata.dev: [NWS warnings and watches by county](https://usdata.dev/datasets/noaa/nws-vtec-events/)
- Studies: [How long before the 6 May 2024 Osage County tornado was a tornado warning issued?](https://usdata.dev/studies/warning-lead-time/)

### Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `phenomena` | Two-letter VTEC phenomena such as TO or SV; requires significance. |
| `significance` | One-letter VTEC significance such as W, A, or Y; requires phenomena. |
| `ugc` | One NWS UGC code in place of a location: a county such as OKC113, or a forecast zone such as OKZ054, which is the only way to reach zone-based products. |

### Variables

| Variable | Units | Meaning |
|---|---|---|
| `vtec_year` | — | Year the event's VTEC event id belongs to |
| `iso_issued` | ISO 8601 UTC | When the event was issued for this UGC |
| `issued` | UTC | The same instant as YYYY-MM-DD HH:MM |
| `iso_expired` | ISO 8601 UTC | When the event expired or was cancelled for this UGC |
| `expired` | UTC | The same instant as YYYY-MM-DD HH:MM |
| `eventid` | — | VTEC event number, unique per office, phenomena, significance, and year; IEM-assigned before VTEC |
| `phenomena` | — | Two-letter VTEC phenomena code, such as TO or SV |
| `significance` | — | One-letter VTEC significance code, such as W warning, A watch, Y advisory |
| `hvtec_nwsli` | — | NWS location identifier of a hydrologic event's forecast point; empty otherwise |
| `wfo` | — | Issuing forecast office; the present-day office for events before 2005 |
| `ugc` | — | The UGC code the row is for |
| `product_id` | — | IEM identifier of the issuing text product |
| `name` | — | Phenomena and significance in words, such as Tornado Warning |
| `ph_name` | — | Phenomena in words |
| `sig_name` | — | Significance in words |
| `url` | — | Path of the event's page on the IEM site |

### Catalog facts

- Availability: since 0.22
- Domain: Severe weather
- Spatial resolution: One county, parish, or forecast zone per request, by NWS UGC code
- Temporal resolution: Issuance and expiry to the minute
- Updates: Not stated by IEM, which processes the live NWS product stream; events before 2005 come from an NWS database dump rather than from VTEC
- Terms of use: <https://mesonet.agron.iastate.edu/disclaimer.php>
- Citation: National Weather Service watch, warning, and advisory products, as archived and served by the Iowa Environmental Mesonet of Iowa State University, accessed via usdata
- Catalog date range: 1986-01-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://mesonet.agron.iastate.edu/info/datasets/vtec.html)
- License: Public domain (NWS products; IEM materials are public domain, attribution appreciated)
- Transport: `http`
- Adapter: `usdata.providers.noaa.nws_vtec:NwsVtecEvents`
