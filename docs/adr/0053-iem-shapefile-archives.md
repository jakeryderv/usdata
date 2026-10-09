# 0053: IEM warning and outlook archives are whole zipped shapefiles, one per UTC month, rewritten canonically

Status: accepted. Date: 2026-10-08. Applies
[ADR 0036](0036-nws-events-by-issuance-and-county.md) to geometries, and the
canonical-form rule of [ADR 0039](0039-credentialed-sources.md) to an answer that
differs between identical requests.

## Context

`noaa:nws-warnings` had been planned since the registry began, held back for
want of a shapefile reader; the roadmap tied it, and SPC convective outlooks,
to choosing a geospatial reader. Both archives are the Iowa Environmental
Mesonet's: NWS keeps no warning archive behind its API, and SPC none behind a
query. A severe-weather prediction study needs both: warning geometries as
targets, and the outlooks issued before a moment as context.

IEM serves each two ways. Its JSON API has GeoJSON services
(`/api/1/vtec/sbw_interval.geojson`, `/api/1/nws/spc_outlook.geojson`), and its
GIS download services (`watchwarn.py`, `outlooks.py`) build a zipped shapefile
for a window. Probing both on 2026-10-08 found:

1. **Only the shapefile services hold the whole archive.** The GeoJSON warning
   service returns storm-based polygons only. The shapefile service returns
   every VTEC product: 3,563 rows for 6 May 00Z to 7 May 12Z 2024, among them
   466 county rows of tornado watches and 224 of tornado warnings beside the
   100 tornado warning polygons. `accept=geojson` is refused with a 422; the
   only other geometry format is KML. The GeoJSON outlook service returns one
   cycle's canonical outlook by valid date, so it cannot be asked what was
   issued in a span, and drops the superseded issuances.
2. **The answer differs between identical requests.** Each zip member is
   stamped with the time the zip was built, and the DBF header with the date.
   Every member's content was otherwise identical byte for byte across
   requests.
3. **The windows select by issuance, end-exclusive to the minute, and accept
   seconds.** Warnings select on `ISSUED`, the event's start as last updated,
   not `INIT_ISS`; outlooks on `PRODISS`, the product's issuance, not the
   valid period.
4. **Requests are capped**: a year of warnings unless narrowed by state, office,
   or phenomena, and ten outlook years. A year of every warning product is
   335 MB zipped.
5. **An outlook window with nothing in it is answered with a line of text**,
   `ERROR: no results found for your query`, with status 200; a warning window
   with nothing is an empty shapefile.

## Decision

**Both datasets read the shapefile services and deliver the zip whole, with no
reader.** Fully supporting the archive means every product and every
issuance, which only those services return. The registry's `reader` is null,
as for the damage surveys' GeoJSON ([ADR 0051](0051-arcgis-feature-layers-and-damage-surveys.md));
geopandas or pyshp opens the zip. A geospatial reader stays a separate
decision, with three formats now waiting on it instead of none.

**`fetch` writes a canonical zip, and `transformations` says so.** The same
members in the same order, each stored uncompressed, stamped 1980-01-01 00:00,
with no extra fields and fixed platform and permission bits, and the DBF's
last-update date set to 1980-01-01. Without it no lockfile could pin an asset:
a restore the next day would fail its checksum. Members are stored rather than
deflated because deflate's output depends on the zlib a machine links, and a
lockfile must restore on any machine.

**A window is split at UTC month boundaries, one asset each.** Each request
stays far under both caps whatever filters are given, an asset is a size one
download holds, and a long window's assets are stable as it grows. The end
sent is the inclusive end plus one second, as for `noaa:nws-vtec-events`.

**The window is the service's: issuance, documented, not widened.** As in ADR
0036. For warnings the guide names `ISSUED` and recommends filtering on
`INIT_ISS` for "known before a moment", since a product that begins in the
future has a later `ISSUED`. The service's "valid at an instant" mode is not
exposed, since a usdata window is a span.

**An outlook window with no results is written as a zip with no members.** It
is the honest form of "nothing was issued", it keeps a month that happens to
hold nothing from failing a multi-month fetch, and the same transformation
line covers it. Any other non-zip answer is an error that quotes it.

**Places: a state for warnings, none for outlooks.** Warnings take a state
location (IEM's `states` filter) or `wfo`, and refuse a county by naming
`noaa:nws-vtec-events`; a box is refused as for every place-keyed source.
Outlooks are national and refuse every spatial filter. WPC excessive rainfall
outlooks, which the outlook service also serves, are not SPC products and are
left out.

## Alternatives

- **GeoJSON from IEM's API.** No reader question and no canonical form needed,
  but it is not the archive: no watches, advisories, or county rows, and no
  outlook history by issuance. Rejected as partial support presented as full.
- **IEM's pregenerated yearly zips.** Static files, but the current year's is
  rebuilt daily, each is a year at a time with no filter, and every product
  together is hundreds of megabytes.
- **Keep IEM's bytes and record a looser checksum.** The content-addressed
  cache and lockfile verify whole files; a second notion of equality would be
  a new contract for one source.
- **Deflate at a fixed level.** Smaller files, but reproducible only on
  machines with the same deflate implementation; zlib-ng, which some
  distributions ship in place of zlib, compresses differently.
- **Raise on an empty outlook window.** Correct for a one-month window, but
  fails a long fetch over one quiet month.

## Consequences

Fetched files are four to five times the size IEM sends: 1.8 MB became 8.3 MB
for one evening of every warning product. Narrowing with `events` or
`storm_based` matters for long windows. The canonical form depends on
`zipfile`'s layout; a Python release that changes it would change checksums,
which an offline test pinning the checksum of one canonicalized zip would show.

Rows are each event's latest state, and IEM corrects both archives in place,
so a restore can fail its checksum on revised data rather than return it
silently, as for any source revised in place. `usdata[...]` gains no
dependency; the walkthroughs read the zips with pyshp from the examples group.
