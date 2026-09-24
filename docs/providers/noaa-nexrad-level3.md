# NEXRAD Level III products

Available since v0.15 as `noaa:nexrad-level3`. The public
`unidata-nexrad-level3` bucket holds derived single-radar products as flat keys
`SITE_PRODUCT_YYYY_MM_DD_HH_MM_SS`, one object per product per volume scan. The
site is the radar's ICAO id without its first letter (`KTLX` is `TLX`,
`PABC` is `ABC`); the adapter maps ids for you, so queries still use `KTLX`.
The bucket begins on 2020-03-30 and keeps everything since. Provide both
timestamps, a radar or geographic query, and the products you want:

```sh
usdata fetch noaa:nexrad-level3 -p site=KTLX -p products=N0B,NMD \
  --start 2024-05-06T20:00Z --end 2024-05-06T20:30Z --dry-run
```

Site selection follows [Level II](noaa-nexrad.md): `site` or `sites`, radars
inside a bounding rectangle, or `nearest`. UTC bounds include both endpoints
and span at most 31 days per query. A window that starts before 2020-03-30 is
rejected before any request and names the NCEI archive, which this adapter
does not reach.

--8<-- "_snippets/utc-window.md"

## Products

`products` is required, case-insensitive, and validated against the codes
below; an unknown code is rejected by name before any request. Each code
selects distinct whole files; it is a parameter rather than a `variables`
filter, so the adapter rejects `variables` and the entry declares
`variable_subset: false`. Ask in an issue to extend the list.

For the moment products the digit or letter after `N` selects the elevation
slot: `0` is the lowest tilt, and `1`, `2`, `3`, `A`, and `B` are higher slots
whose exact angles depend on the volume coverage pattern in use.

| Code | Product | Typical size (KTLX, 2026-09) |
|---|---|---|
| `N?B` | Base reflectivity, super-resolution (since 2022-02-18) | 240 kB at `N0B`, smaller aloft |
| `N?G` | Base velocity, super-resolution (since 2022-02-18) | 190 kB at `N0G` |
| `N?Q` | Base reflectivity, 256 levels (retired 2022-09-08; use `B`) | 37 kB |
| `N?U` | Base velocity, 256 levels (retired 2022-09-08; use `G`) | 114 kB |
| `N?S` | Storm-relative mean radial velocity | 27 kB |
| `N?C` | Correlation coefficient | 157 kB |
| `N?X` | Differential reflectivity | 144 kB |
| `N?K` | Specific differential phase | 11 kB |
| `N?H` | Hydrometeor classification | 15 kB |
| `NCR` | Composite reflectivity | 37 kB |
| `EET` | Enhanced echo tops | 1.5 kB |
| `DVL` | Digital vertically integrated liquid | 7 kB |
| `NMD` | Mesocyclone detection | 150 B when empty, 2 kB with detections |
| `NST` | Storm tracking information | 10 kB |
| `NTV` | Tornado vortex signature (retired 2022-05-24) | 2 kB |
| `NVW` | VAD wind profile | 9 kB |
| `DHR` | Digital hybrid-scan reflectivity | varies |
| `HHC` | Hybrid hydrometeor classification | varies |
| `DAA` | Digital one-hour precipitation accumulation | 224 B when dry |
| `DTA` | Digital storm-total precipitation accumulation | 1.8 kB |
| `DSP` | Digital storm-total precipitation | varies |
| `OHA` | One-hour precipitation accumulation | varies |

Retired codes remain in the list so 2020–2022 requests can still name them;
requesting one for a later date lists nothing. Sizes are medians from one
clear-air day and grow with weather. A radar produces roughly 120 to 390 files
per product per day depending on its scan strategy, so a day of one product is
one listing request and up to a few hundred small downloads.

The bucket holds what the Unidata feed captured, and an empty or short listing
inside the archive period is not an error; the adapter does not fill it from
NCEI. A short listing is not always a feed gap. On 2024-05-06 KTLX's echo-top
files run from 20:34 UTC, while its mesocyclone and storm-track files begin at
20:42:46, the scan whose header shows the radar leaving clear-air VCP 35 for
precipitation VCP 212 ([walkthrough](https://usdata.dev/datasets/noaa/nexrad-level3/)).
Check the volume coverage pattern before reading missing files as lost ones.

## No reader

Level III is a separate binary format from Level II, and this release ships
**no reader** for it. `FetchedAsset.open()` raises `UnsupportedFormat` naming
`fetched.path`. Decode the cached file with
[Py-ART](https://arm-doe.github.io/pyart/API/generated/pyart.io.read_nexrad_level3.html)
or another Level III decoder:

```python
import pyart

radar = pyart.io.read_nexrad_level3(item.path)
```

Provenance, checksums, lockfiles, and restoration work as for every other
dataset; only decoding is external.

See the [service research notes](noaa-services.md#nexrad-level-iii-products)
for dated upstream probes.

## Metadata sources

Every value in the catalog entry's resolution, cadence, citation, terms, variables, and
limits comes from one of these pages. A field the agency does not publish is left empty
rather than estimated.

- Temporal resolution and updates: the file counts and feed gaps documented above,
  measured from the bucket; the bucket holds what the Unidata feed captured.
- Citation and terms: the [NODD registry
  entry](https://registry.opendata.aws/noaa-nexrad/) and the [NOAA Open Data
  Dissemination](https://www.noaa.gov/information-technology/open-data-dissemination)
  statement it quotes.
- Variables: the product-code table above, which is the exact list this adapter accepts.
- Longest query window: `MAX_WINDOW` in `usdata.providers.noaa.nexrad_level3`.
- Spatial resolution and latency are empty: no upstream page states a per-product grid
  spacing or a lag for this bucket.

[All NOAA datasets](noaa.md).

--8<-- "generated/catalog/noaa/nexrad-level3.md"
