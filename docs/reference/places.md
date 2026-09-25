# Places

What a place lookup returns and why it is a rectangle is explained in
[time and place](../concepts/time-and-place.md#places). `build_query(location=...)`,
manifest `location`, and CLI `--location` (also `--state`) share one bundled
offline table.

A location resolves to two things, both kept on the query: `query.bbox`, the
rectangle, and `query.place`, the state or county itself with its FIPS code
(`place.geoid`, `place.state_fips`, `place.county_fips`) and its state's postal
code (`place.state`). A `bbox` or a
`lat`/`lon` sets only the rectangle, since a box names no place.
`usdata.query.find_place(name)` returns both; `resolve_place(name)` returns the
rectangle alone.

## Input forms

| Input | Meaning |
|---|---|
| `Oklahoma`, `OK`, `"40"` | State name, postal code, or two-digit FIPS. |
| `Cleveland County, OK`, `Cleveland, Oklahoma`, `"40027"` | County and state, or five-digit county FIPS. |
| `Fairfax city, VA` | A county equivalent, distinct from `Fairfax County, VA`. |
| `Capitol Planning Region, CT`, `"09110"` | Connecticut's current county-equivalent planning region. |
| `Hartford County, CT`, `"09003"` | One of Connecticut's eight counties before 2022. See [Connecticut](#connecticut). |

Matching ignores case, repeated whitespace, and spacing around commas. A bare
county name such as `Washington County` works only when unambiguous; otherwise
the error lists candidates and asks for a state or FIPS. State names and postal
codes take precedence over bare county aliases. Quote FIPS codes in YAML and
Python to keep leading zeros; numeric values and shortened codes are not
accepted.

## Coverage

| | Count | Source |
|---|---|---|
| States, DC, and territories | 56 | Census Bureau 2025 cartographic boundary files, 1:500,000 |
| Counties and equivalents | 3,235 | Same |
| Connecticut counties before 2022 | 8 | Census Bureau 2021 cartographic boundary file, 1:500,000 |

Territories covered: American Samoa, Guam, the Northern Mariana Islands,
Puerto Rico, and the U.S. Virgin Islands. Boxes are the minimum and maximum
longitude and latitude of every polygon vertex.

## Antimeridian

A box cannot wrap across 180 degrees of longitude. A place whose polygons lie
on both sides of it keeps only its western-hemisphere polygons, so no box is
wider than 180 degrees. Two places are clipped this way: Alaska and Aleutians
West Census Area, whose boxes end at 179.146711°W and omit the Near Islands
(Attu) and part of the Rat Islands, between 172.46°E and 179.78°E. The bundled
`places.sources.json` records each clip and the box it dropped. For those
islands, pass a `bbox` or name sites explicitly.

## Connecticut

In 2022 Connecticut's nine planning regions replaced its eight counties as
county equivalents, with new FIPS codes (`09110` to `09190`). Census geography
from 2022 on, and so the 2025 files, holds only the regions. Several sources
did not follow: OpenFEMA, AQS, and the NWS still key Connecticut by the
counties (`09001` to `09015`), and have no rows under a region's code.

The table therefore holds both. The eight counties come from the 2021 files,
the last vintage to hold them, and resolve like any county: `Hartford County,
CT`, `Hartford, Connecticut`, or `"09003"`, with `place.kind` `county`. No
county shares a name with a region, so every region lookup is unchanged.

The two do not nest in each other. A region overlaps each county it shares a
town with, per the Census
[town crosswalk](https://www2.census.gov/geo/docs/reference/ct_change/ct_cou_to_cousub_crosswalk.txt):

| Planning region | Counties before 2022 it overlaps |
|---|---|
| Capitol (`09110`) | Hartford, Tolland |
| Greater Bridgeport (`09120`) | Fairfield |
| Lower Connecticut River Valley (`09130`) | Middlesex, New London |
| Naugatuck Valley (`09140`) | Fairfield, Hartford, Litchfield, New Haven |
| Northeastern Connecticut (`09150`) | New London, Tolland, Windham |
| Northwest Hills (`09160`) | Hartford, Litchfield |
| South Central Connecticut (`09170`) | New Haven |
| Southeastern Connecticut (`09180`) | New London, Windham |
| Western Connecticut (`09190`) | Fairfield, Litchfield |

`usdata.query.legacy_counties(place)` returns those counties for a region, and
nothing for any other place. A source keyed by the old codes refuses a region
with a message naming them, rather than answering it with nothing. A source
that selects by rectangle takes either kind. The bundled `places.sources.json`
records the 2021 archive and the crosswalk with their hashes; in `places.csv`
the eight rows have kind `legacy_county`, and each region lists its counties
in `legacy_counties`.
