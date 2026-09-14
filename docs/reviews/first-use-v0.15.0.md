# First-use review: v0.15.0

Observed on 2026-09-14 UTC against the published `usdata[pandas,grib]==0.15.0`
package and the maintained [getting-started walkthrough](../index.md).
The walkthrough, an installed-package fetch from each of the six datasets this
release added, the GRIB2 reader on both grid types, network-blocked query
validation for every new adapter, all twelve live tests for the new modules,
and the tornado classification notebook passed. No SDK or adapter changes were
needed. One usage observation is recorded below.

## Method and results

The published package was installed with uv into a new virtual environment
outside the repository on Linux with Python 3.14.7, pandas 3.0.5, pydantic
2.13.5, httpx 0.28.1, ecCodes 2.48.2, and xarray 2026.7.0. The imported
package came from that environment's `site-packages`, with no editable
installation. The walkthrough used fresh, isolated temporary cache directories;
user caches were untouched. The Python and manifest blocks were extracted from
the maintained guide. The release baseline was `299d9d9` (v0.15.0). The first
install attempt, seconds after publication, could not resolve 0.15.0 from a
cached index; a refreshed resolve succeeded.

| Step | Observed result |
| --- | --- |
| Search precipitation in Oklahoma | Completed successfully; seven supported datasets returned, now including `noaa:mrms`. |
| Inspect `noaa:ghcn-daily` | Dataset information and both accepted parameters displayed successfully. |
| Fetch station `USW00013967`, May 6–7, 2024, `PRCP,TMAX` | One 209-byte CSV downloaded. |
| Execute the guide's Python reading example | Two observation rows opened from the cached file. |
| Pull and verify the guide's manifest | Lockfile written; all cached assets matched. |
| Restore into a second empty cache | Pinned source downloaded again; restored bytes passed verification. |

## Release-specific checks

This release added six datasets and the GRIB2 reader, so the checks fetched one
small asset from each dataset through the installed CLI around the Oklahoma
tornado of 04:39 UTC on 2024-05-07 that the new example uses, then opened the
results through the installed SDK.

| Dataset | Installed-package fetch | Opened |
| --- | --- | --- |
| `noaa:goes-glm` | Two 20-second GOES-16 files, 425,788 and 646,951 bytes | `MissingReaderDependency` naming `usdata[netcdf]`, which this environment omitted |
| `noaa:spc-tornado-reports` | `2024_torn.csv`, 230,094 bytes | 1,873 rows, 1,791 with `sg=1` |
| `noaa:nexrad-level3` | KTLX `EET` at 04:40:53 UTC, 15,740 bytes | `UnsupportedFormat` naming `fetched.path` and Py-ART |
| `noaa:mrms` | `RotationTrackML30min_00.50` at 04:38 UTC, 182,758 bytes | 7000 × 14000 grid in 1.07 s, maximum 26, 1.27 GB peak resident memory |
| `noaa:hrrr` | Dry run listed the 04Z surface analysis without downloading | Not fetched here; covered by the live test below |
| `noaa:gfs` | 00Z one-degree analysis, 42,259,722 bytes | Surface CAPE 181 × 360 in 0.45 s with `select`; without `select`, a `ValueError` naming 696 messages and the keys to pass |

With the network blocked, the installed package rejected each of these before
any request, with a `QueryError` naming the problem: a two-day GLM window, GLM
satellite 15, a `channel` parameter passed to GLM, SPC reports before 1950, a
location passed to SPC, Level III with no products, an unknown Level III code,
a Level III window before 2020-03-30, an MRMS product in the wrong case (the
message suggests the right one), a two-day MRMS window, an MRMS window before
2020-10-14, HRRR with no cycle, HRRR forecast hour 30 on a 03Z run, HRRR
`file=subh`, GFS cycle 3, GFS hour 121 at 0.25 degrees, and a GFS resolution of
`2p00`.

The checkout's live tests for GLM, SPC, Level III, MRMS, HRRR, and GFS were run
with explicit live opt-in, pytest's temporary caches, and the pandas, grib,
netcdf, and radar extras installed. All twelve passed in 58 s, with no skips,
including the 150 MB HRRR surface file and the GRIB2 reader opening HRRR and
GFS surface CAPE.

The tornado classification notebook, which joins one Storm Events report to a
KTLX volume, nine MRMS rotation grids, and 69 GLM files and builds a twelve-row
labeled table, was executed in a fresh kernel against the live services. It
passed without changes to its saved outputs.

## Observation

A date-only `--end` means midnight at the start of that day, as every dataset
guide states. For the model datasets this matters more than elsewhere: a query
for `--start 2024-05-07 --end 2024-05-07` with `cycle=4` spans no time and
correctly reports that no 04Z initialization falls inside it, while the same
window with `cycle=0` succeeds. The HRRR and GFS guides show explicit timestamps
in every example. No change was made; a first-time user reading only the CLI
help could still be surprised, and a later review may decide whether the
model adapters should say so in their rejection message.

## Limits

This review is a dated upstream-health and first-use snapshot. It covers one
Linux/Python installation, the primary station walkthrough, the six datasets
and reader added in this release, and one notebook. It did not test macOS,
where the grib extra needs the ecCodes library from conda-forge or Homebrew,
nor Windows. It does not replace the full scheduled live suite or the offline
platform/dependency matrix. Upstream services can fail or revise files later.
Keep manifests, lockfiles, and cached bytes together; checksums detect changes
but do not archive unavailable upstream revisions.

The earlier [v0.14.0 review](first-use-v0.14.0.md),
[v0.13.0 review](first-use-v0.13.0.md),
[v0.12.0 review](first-use-v0.12.0.md), and
[v0.10.0 review](first-use-v0.10.0.md) retain their original evidence.
