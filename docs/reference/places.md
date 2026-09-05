# State and county lookup

Available from source for v0.5. `build_query(location=...)`, manifest `location`,
and CLI `--location` (also `--state`) use the same bundled, offline table.

| Input | Meaning |
|---|---|
| `Oklahoma`, `OK`, `"40"` | A state name, postal code, or two-digit FIPS. |
| `Cleveland County, OK`, `Cleveland, Oklahoma`, `"40027"` | County/state name or five-digit county FIPS. |
| `Fairfax city, VA` | A county equivalent; distinct from `Fairfax County, VA`. |
| `Capitol Planning Region, CT`, `"09110"` | Connecticut's current county-equivalent planning region. |

Matching ignores case, repeated whitespace, and spacing around commas. Bare
qualified names such as `Washington County` work only when unambiguous;
otherwise the error lists candidates and asks for a state or FIPS. State names
and postal codes take precedence over bare county aliases. Quote FIPS in YAML
and Python to preserve leading zeros; numeric values and shortened codes are
not accepted. Arbitrary city/address geocoding is outside this table.

## Coverage and geometry

The table contains **56 states/DC/territories** and **3,235 counties or
equivalents**, from the Census Bureau's 2025 1:500,000 cartographic boundary
files. Coverage includes all 50 states, DC, American Samoa, Guam, the Northern
Mariana Islands, Puerto Rico, and the U.S. Virgin Islands.

A result is a longitude/latitude rectangle enclosing a generalized boundary,
not the boundary itself. It can include neighboring counties, ocean, or other
points outside the named region. It is not suitable for exact jurisdictional
membership or legal boundary determinations. Providers interpret this rectangle
according to their own selection rules; NEXRAD falls back to the nearest radar
when none is inside it. Use explicit stations/sites for exact selection.

`BBox` cannot represent a west-to-east wrap across the antimeridian. Generation
keeps the minimum and maximum longitudes of every polygon vertex. Alaska and
Aleutians West therefore have conservative envelopes spanning more than 350
longitude degrees. Prefer a local bbox or explicit sites there; these envelopes
can otherwise select far more data than intended. Queries requiring a wrapped
region must be split into separate non-wrapping boxes by the caller.

## Provenance and regeneration

The [Census cartographic boundary page](https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html)
describes these generalized files. Source archives:

- [2025 states, 1:500,000 KML](https://www2.census.gov/geo/tiger/GENZ2025/kml/cb_2025_us_state_500k.zip)
- [2025 counties, 1:500,000 KML](https://www2.census.gov/geo/tiger/GENZ2025/kml/cb_2025_us_county_500k.zip)

`scripts/build_places.py` reads KML with the Python standard library and writes
`src/usdata/data/places.csv` plus `places.sources.json`. The sidecar records
source URLs, archive SHA-256 hashes, counts, vintage, scale, and CSV checksum.
No geospatial runtime dependency or online geocoder is required.

```sh
just places                           # download pinned 2025 archives and generate
just places --check                   # download and compare with committed outputs
just places --source-dir /path/to/zips --check  # reproduce offline from saved archives
```

Never hand-edit the CSV. Updating the vintage requires updating the generator,
expected coverage tests, source notes, and changelog. Ordinary CI validates
bundled counts, unique FIPS, valid bounds, aliases, and the CSV checksum without
network access; source regeneration is an explicit maintenance task.
