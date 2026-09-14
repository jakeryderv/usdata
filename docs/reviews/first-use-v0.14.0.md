# First-use review: v0.14.0

Observed on 2026-09-14 UTC against the published `usdata[pandas]==0.14.0`
package and the maintained [getting-started walkthrough](../index.md).
The walkthrough, the live checks for both datasets this release added, their
query validation, and one notebook execution passed. No SDK or adapter changes
were needed.

## Method and results

The published package was installed with uv into a new virtual environment
outside the repository on Linux with Python 3.14.7, pandas 3.0.5, pydantic
2.13.5, and httpx 0.28.1. The imported package came from that environment's
`site-packages`, with no editable installation. The walkthrough used fresh,
isolated temporary cache directories; user caches were untouched. The Python
and manifest blocks were extracted from the maintained guide. The release
baseline was `9b43bba` (v0.14.0).

| Step | Observed result |
| --- | --- |
| Search precipitation in Oklahoma | Completed successfully; six supported station and radar datasets returned, now including `noaa:lcd`. |
| Inspect `noaa:ghcn-daily` | Dataset information and both accepted parameters displayed successfully. |
| Fetch station `USW00013967`, May 6–7, 2024, `PRCP,TMAX` | One 209-byte CSV downloaded. |
| Execute the guide's Python reading example | Two observation rows opened from the cached file. |
| Pull and verify the guide's manifest | Lockfile written; all cached assets matched. |
| Restore into a second empty cache | Pinned source downloaded again; restored bytes passed verification. |
| Verify and restore the inputs with DNS and socket connections blocked | Both succeeded without network access; the restored file opened with two rows. |

## Release-specific checks

This release added `noaa:lcd` and `noaa:coops-tide-predictions`, so the checks
targeted those two adapters from both the installed package and the checkout.

From the installed package, `usdata info` listed each dataset's provider
parameters without network access. A three-day LCD fetch for Oklahoma City's
airport returned one 58,711-byte CSV with 125 reports, mostly hourly `FM-15`
observations, and a one-day high/low tide-prediction fetch for Cedar Key on
September 26, 2024 returned four extremes with alternating `H` and `L` types.

With the network blocked, the installed package rejected each of these before
any request, with a `QueryError` naming the problem: a tide-prediction interval
of `7`, a six-digit CO-OPS station, a missing datum, free text passed to either
adapter, LCD `stations` combined with a `location`, an LCD query with no
station or location, and LCD `units=kelvin`.

The checkout's live tests for LCD and CO-OPS tide predictions were run with
explicit live opt-in and pytest's temporary caches. Both passed, with no skips:
the LCD test confirmed three daily summaries beside at least sixty hourly
reports and that each day's hourly maximum stayed within the daily maximum; the
prediction test aligned six-minute predictions with observations at the same
timestamps, bounded the high/low count, and restored exact bytes from the
lockfile.

The storm-surge notebook, which subtracts tide predictions from observed water
levels during Hurricane Helene and places the peak against the HURDAT2 track,
was executed in a fresh kernel against the live services. It passed without
changes to its saved outputs.

## Limits

This review is a dated upstream-health and first-use snapshot. It covers one
Linux/Python installation, the primary station walkthrough, the two adapters
added in this release, and one notebook. It does not replace the full scheduled
live suite or the offline platform/dependency matrix. Upstream services can fail
or revise files later. Keep manifests, lockfiles, and cached bytes together;
checksums detect changes but do not archive unavailable upstream revisions.

The earlier [v0.13.0 review](first-use-v0.13.0.md),
[v0.12.0 review](first-use-v0.12.0.md), and
[v0.10.0 review](first-use-v0.10.0.md) retain their original evidence.
