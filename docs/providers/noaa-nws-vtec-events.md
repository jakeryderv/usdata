# NWS watches and warnings by county

`noaa:nws-vtec-events`, available since v0.22.0, uses the
[Iowa Environmental Mesonet](https://mesonet.agron.iastate.edu/info/datasets/vtec.html)
archive of National Weather Service products, at
`https://mesonet.agron.iastate.edu/json/vtec_events_byugc.py`, checked on
2026-09-18. IEM is part of Iowa State University and is not an NWS endpoint; it
is the maintained archive, because the official `api.weather.gov/alerts` keeps
none. A query there for May 2024 returns no features.

One row is one event issued for one UGC, the NWS code for a county or a forecast
zone: its issuance and expiry, its VTEC phenomena and significance, the issuing
office, and the product id. There are no coordinates and no polygons; those are
the planned [`noaa:nws-warnings`](../generated/catalog/noaa.md).

- A place is a named county: `--location "Osage County, OK"` or a quoted
  five-digit FIPS code. It becomes the county's UGC, the state's postal code,
  `C`, and the county FIPS code, so Osage County is `OKC113`. A `bbox` or
  `lat`/`lon` is refused, since a rectangle names no county
  ([ADR 0034](../adr/0034-query-keeps-the-resolved-place.md)). A state is
  refused by name: the service answers for one UGC at a time.
- `-p ugc=OKZ054` names a code explicitly, in place of a location. It is the
  only way to reach a forecast zone. See
  [counties and zones](#counties-and-zones).
- Both timestamps are required, in UTC, to the second. The window selects
  events by **when they were issued**, inclusive at both ends. See
  [issued, not in effect](#issued-not-in-effect).
- `-p phenomena=TO -p significance=W` narrows to one event type. The service
  requires the pair together, and so does the adapter.
- `variables` is rejected: the CSV columns are fixed. Free text is rejected as
  everywhere.
- Listing makes no request, since the service offers no count. A window with no
  events therefore fetches a header and no rows rather than listing nothing, and
  an explicit `ugc` the service does not know (`OKC999`) does the same. A county
  location cannot be wrong that way, because it comes from the place table.
- The pandas reader opens the CSV. Pass
  `parse_dates=["iso_issued", "iso_expired"]` for timezone-aware instants;
  `issued` and `expired` are the same instants in a second format with no
  timezone.
- Sizes are not known before download. Access was verified without credentials.
  Forty years of one county is 3,121 rows, and the service applied no cap.

```sh
usdata fetch noaa:nws-vtec-events --location "Osage County, OK" --start 2024-05-06T18:00Z --end 2024-05-07T12:00Z
usdata fetch noaa:nws-vtec-events --start 2024-01-01 --end 2024-12-31 -p ugc=OKZ054
```

## What the service does not say

Three behaviours were found by getting them wrong, and the adapter is built
around them ([ADR 0036](../adr/0036-nws-events-by-issuance-and-county.md)).

**The date-only parameters are unreliable.** `sdate=2024-05-07&edate=2024-05-08`
returns no rows. The same span as `sts=2024-05-07T00:00Z&ets=2024-05-09T00:00Z`
returns 13, all issued on 7 May UTC. Six windows were tried and no rule, UTC
dates or Central ones, inclusive ends or exclusive, explains the date-only
results. The service's changelog says `sts` and `ets` were added on 2025-01-20
"for a more explicit datetime range". The adapter sends only those. They need a
timezone, accept any offset, and are half-open: `[01:34, 01:35)` finds the
warning issued at exactly 01:34:00Z and `[01:33, 01:34)` does not. A usdata
window's end is inclusive, so the adapter sends the end plus one second.

### Issued, not in effect

The Tornado Watch covering Osage County ran from 19:05 UTC on 6 May 2024 to
03:48 UTC on 7 May. A window of 03:00 to 03:30 UTC, inside it, returns nothing,
because nothing was issued then. The service cannot be asked what was in effect
at a moment; only what was issued during a span.

To ask what was in effect, widen the window backwards far enough to catch what
was still running, and compare the two instants yourself:

```python
frame = item.open_csv(parse_dates=["iso_issued", "iso_expired"])
moment = pd.Timestamp("2024-05-07T02:12Z")
in_effect = frame[(frame.iso_issued <= moment) & (frame.iso_expired > moment)]
```

The adapter does not widen for you. How far back is enough depends on the
product, minutes for a warning and hours for a watch, so any built-in lookback
would be a guess, and would return rows nobody asked for.

### Counties and zones

NWS issues some products by county and others by forecast zone. A county code
reaches the first kind only. `OKC113` for all of 2024 returns 151 events of six
types: `TO.W`, `SV.W`, `FF.W`, `TO.A`, `SV.A`, and `FA.Y`. Osage County's forecast
zone that year, `OKZ054`, returns 87 events of twelve other types, among them
`EH.W`, `FW.W`, and `WW.Y`: heat, fire weather, and winter weather.

A county location cannot name a zone, and the adapter does not map one to the
other, because the mapping is neither one-to-one nor fixed. `OKZ054` covered all
of Osage County through April 2026. From May 2026 the county is three zones,
`OKZ154`, `OKZ254`, and `OKZ354`, which return nothing for 2024, while `OKZ054`
returns nothing after the change. Which code is right depends on the date being
asked about. Zone-based products are reached only through `ugc`, and finding
the zone for a place and a date is left to the
[NWS zone maps](https://www.weather.gov/pimar/PubZone).

## The archive before 2005

IEM's dataset notes give the depth as "Most WWA types back to 2008 or 2005, an
archive of Flash Flood Warnings goes back to 2002 or so, and Tornado / Severe
Thunderstorm Warnings goes back to 1986". Probing Oklahoma County for 1986
returned 40 rows of `TO.W`, `SV.W`, and `FF.W`, so some flash flood warnings are
present earlier than the notes say.

VTEC itself dates from 2005. IEM says the earlier events come from "a database
dump" of an NWS archive covering 1986 to 2005, which "was atomic to a local
county/parish, so some logic was done to merge multiple counties when they
spatially touched and had similiar issuance timestamps", and which "did not
contain the issuance forecast office, so ... the present day WFOs were used".
Treat `eventid` and `wfo` before 2005 as IEM's reconstruction rather than as
issued.

Probes used to verify the endpoint and these behaviours:

```sh
U='https://mesonet.agron.iastate.edu/json/vtec_events_byugc.py'
curl "$U?ugc=OKC113&sts=2024-05-06T18:00:00Z&ets=2024-05-07T12:00:01Z&fmt=csv"   # 14 events
curl "$U?ugc=OKC113&sdate=2024-05-07&edate=2024-05-08&fmt=csv"                   # header only
curl "$U?ugc=OKC113&sts=2024-05-07T00:00Z&ets=2024-05-09T00:00Z&fmt=csv"         # 13 events
curl "$U?ugc=OKC113&sts=2024-05-07T03:00Z&ets=2024-05-07T03:30Z&fmt=csv"         # header only, inside the watch
curl "$U?ugc=OKC113&sts=2024-05-06T18:00Z&ets=2024-05-07T12:00Z&phenomena=TO&fmt=csv"   # 422: needs significance
curl "$U?ugc=OKC999&sts=2024-05-06T18:00Z&ets=2024-05-07T12:00Z&fmt=csv"         # 200, header only
```

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Coverage, depth, and the caveats on events before 2005: IEM's
  [VTEC dataset notes](https://mesonet.agron.iastate.edu/info/datasets/vtec.html).
- Parameters, the `sts` and `ets` changelog entry, and the phenomena and
  significance filter: the service's own help page, at the endpoint with `?help`.
- Column meanings: the rows themselves and the
  [NWS VTEC explanation](https://www.weather.gov/vtec/).
- Terms and license: IEM's [disclaimer](https://mesonet.agron.iastate.edu/disclaimer.php),
  which places its materials in the public domain and says attribution "would
  be appreciated". The citation names NWS as the origin and IEM as the archive.
- Update frequency: IEM states none, and the entry says so.
- Latency is empty for the same reason.
- No window limit is declared, because the adapter enforces none.

[NOAA access notes](noaa.md).

--8<-- "generated/catalog/noaa/nws-vtec-events.md"
