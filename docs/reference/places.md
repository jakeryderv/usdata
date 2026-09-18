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

Territories covered: American Samoa, Guam, the Northern Mariana Islands,
Puerto Rico, and the U.S. Virgin Islands. Boxes are the minimum and maximum
longitude and latitude of every polygon vertex; Alaska and Aleutians West span
more than 350 degrees of longitude.
