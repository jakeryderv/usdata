# HURDAT2 best tracks

Available from source for the unreleased v0.12.0 as `noaa:hurdat2`. The National
Hurricane Center publishes its complete best-track database as two anonymous
plain-text files, one for the Atlantic basin and one for the northeast and
north-central Pacific. There is no query interface of any kind: no records API,
no per-storm files, no server-side subsetting. The only sensible asset is one
whole file per basin, so HURDAT2 is the first usdata dataset whose value lives
in the reader rather than the query.

## Selecting a basin

`basin` is the only parameter: `atlantic` (the default) or `pacific`, matched
case-insensitively. Any other parameter, a location or bbox, `variables`, and
text queries are rejected with an error rather than silently ignored, because
none of them can change which bytes are downloaded.

**Dates are rejected too.** Every revision contains the complete record for its
basin, so a `start`/`end` pair would select nothing; recording a requested window
as the asset's time bounds would misdescribe the cached file in the lockfile and
provenance sidecar. Asset time bounds instead report the data span named in the
filename (1851 through the last completed Atlantic season, 1949 onward for the
Pacific). Filter the parsed `time` column locally. `capabilities` are all false.

## Revisions and filenames

The [data directory](https://www.nhc.noaa.gov/data/hurdat/) keeps past
revisions, not only the current pair: it listed 41 files on 2026-09-13, the
oldest a Pacific file revised 2017-04-13. How far back it reaches is the NHC's
choice, so treat it as an archive that happens to be deep rather than a complete
history. Filenames embed the data span and a revision date, such as
`hurdat2-1851-2025-02272026.txt` and `hurdat2-nepac-1949-2025-02272026.txt`.
The basin token is `nepac` for the Pacific and either `atl` or absent for the
Atlantic. Revision dates are `MMDDYY` or `MMDDYYYY` — never `YYYYMMDD` — and a
few names carry a trailing disambiguating letter, so resolution parses the date
rather than sorting filenames as text. The newest data span wins first, then the
newest revision of that span; names that are not real dates, files for the other
basin, and non-local links are ignored.

The complete filename is the stable asset ID, and the URL, original bytes,
size, and checksum are preserved. The directory reports approximate sizes
(`6.8M`), so asset size is left unknown rather than guessed. A lockfile restores
its pinned URL without listing current revisions. When the NHC publishes the next
season's file under a new name, an existing lockfile keeps working as long as the
old file remains online; preserve your cache for long-term reproducibility, and
use `pull(..., force=True)` only when intentionally moving to a new revision.

## Opening the file

`FetchedAsset.open()` uses the pandas extra and selects the `hurdat2` reader from
the dataset id or the `hurdat2-*.txt` filename, so it needs no arguments. It
returns one row per best-track point:

| Column | Meaning |
|---|---|
| `storm_id` | ATCF-style basin, cyclone number, and year, such as `AL042021` |
| `name` | Storm name, or `UNNAMED` |
| `time` | Track-point time, UTC |
| `record_identifier` | `L` landfall, `I` intensity peak, `P` pressure minimum, and the other documented codes; missing on ordinary records |
| `status` | `TD`, `TS`, `HU`, `EX`, `SD`, `SS`, `LO`, `WV`, or `DB` |
| `latitude`, `longitude` | Signed decimal degrees, longitude in [-180, 180]; the source hemisphere letters become signs |
| `max_wind_kt` | Maximum sustained 1-minute surface wind, knots |
| `min_pressure_mb` | Minimum central pressure, millibars |
| `r34_ne_nm` … `r64_nw_nm` | Twelve wind radii: the 34, 50, and 64 kt maximum extent in each quadrant, nautical miles |
| `max_wind_radius_nm` | Radius of maximum wind, nautical miles |

The documented missing sentinels become NaN: `-999` anywhere, and the `-99`
maximum wind left unassigned on a non-developing depression. The NHC format
reference ties `-99` to 1967; in the current Atlantic file it in fact appears 57
times, all on `TD` records between 1971 and 1987, and never in the Pacific file.
Wind radii were best-tracked only from 2004 and the radius of maximum wind only
from 2021, so those columns are mostly NaN in earlier decades; revisions published before
2021 omit the radius-of-maximum-wind field entirely and the reader fills it with
NaN. Numeric columns use float dtype so those gaps are representable; units are
in the column names rather than a synthesized units map. Text columns keep source
strings, and a blank record identifier or status becomes missing rather than an
empty string.

Parsing follows the file's own structure: a header line such as
`AL011851, UNNAMED, 14,` is followed by exactly the number of track-point lines
it declares. A count that does not match, a line with the wrong number of fields,
an unparseable timestamp or coordinate, or text where a measurement belongs
raises `Hurdat2FormatError` from `usdata.readers` (a `ValueError`) naming the
line, rather than returning a partly parsed table.

Archived revisions read the same way, which is what makes a restored lockfile
useful. Two differences show up only in older files. Data lines published before
the 2021 season carry 20 values and a terminating comma instead of 21, so
`max_wind_radius_nm` is NaN. And some revisions write a position east of
Greenwich in the unwrapped 0-360 west convention, continuing a track from `3.3W`
to `358.0W`; the reader normalizes that to `2.0`, the value the NHC itself
published for the same point in a later revision. Of the 41 files listed on
2026-09-13, 39 parse; two carry an upstream typo (a missing comma between
latitude and longitude, and a date written `C0091018`) that the next revision of
the same span corrects, and those raise rather than parse silently.

CSV options (`dtype`, `parse_dates`, `usecols`, `nrows`) do not apply and are
rejected. Opening is local: it never re-fetches, decompresses into the cache, or
changes provenance, which is copied into `frame.attrs["usdata"]`.

## Scientific limits

HURDAT2 is a post-season reanalysis, not an observation archive. Coverage and
accuracy degrade going back in time: storms were missed and intensities
underanalyzed before aircraft reconnaissance (1944 in the western Atlantic) and
before routine satellite imagery (late 1960s), so counting storms per decade
measures observing systems as much as climate. Positions and intensities are
best-track estimates at each time, wind radii are quadrant maxima rather than a
wind field, and `record_identifier` marks why an asynoptic record exists rather
than enumerating impacts. Continental U.S. landfalls are marked for 1851-1970 and
1991 onward; international landfalls only for 1951-1970 and 1991 onward. Track
points for `WV` and `DB` status give a lower-tropospheric vorticity center, not a
surface center. The Pacific file covers the northeast and north-central Pacific
only; it is not a global archive, and `noaa:ibtracs` remains the planned entry
for merged worldwide tracks.

Field meanings, record codes, and era-by-era caveats are documented in the NHC
[Atlantic format reference](https://www.nhc.noaa.gov/data/hurdat/hurdat2-format-atl-1851-2021.pdf)
and [northeast Pacific format reference](https://www.nhc.noaa.gov/data/hurdat/hurdat2-format-nencpac-1949-2021.pdf).
The [manifest example](../examples/hurdat2/README.md) fetches the Atlantic file
and reads it locally. The
[design decision](../adr/0020-hurdat2-whole-file-and-format-reader.md) records the
whole-file and reader contract.

See the [service research notes](noaa-services.md#hurdat2-best-tracks) for dated upstream probes.

[All NOAA datasets](noaa.md).

[Catalog reference](../generated/catalog/noaa/hurdat2.md#catalog-reference).
