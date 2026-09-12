# First-use review: v0.13.0

Observed on 2026-09-12 UTC against the published `usdata[pandas]==0.13.0`
package and the maintained [getting-started walkthrough](../index.md).
The walkthrough, the live checks for every adapter this release changed, the
new query-validation behaviour, and one notebook execution passed. No SDK or
adapter changes were needed.

## Method and results

The published package was installed with uv into a new virtual environment
outside the repository on Linux with Python 3.14.7, pandas 3.0.5, pydantic
2.13.5, and httpx 0.28.1. The imported package came from that environment's
`site-packages`, with no editable installation. The walkthrough used fresh,
isolated temporary cache directories; user caches were untouched. The Python
and manifest blocks were extracted from the maintained guide. The release
baseline was `9389c4a` (v0.13.0).

| Step | Observed result |
| --- | --- |
| Search precipitation in Oklahoma | Completed successfully; five supported station and radar datasets returned. |
| Inspect `noaa:ghcn-daily` | Dataset information and both accepted parameters displayed successfully. |
| Fetch station `USW00013967`, May 6–7, 2024, `PRCP,TMAX` | One 209-byte CSV downloaded. |
| Execute the guide's Python reading example | Two observation rows opened from the cached file. |
| Pull and verify the guide's manifest | Lockfile written; all cached assets matched. |
| Restore into a second empty cache | Pinned source downloaded again; restored bytes passed verification. |
| Verify and restore the inputs with DNS and socket connections blocked | Both succeeded without network access; the restored file opened with two rows. |

## Release-specific checks

This release changed how adapters validate queries and bounded three listings,
so the checks targeted that behaviour rather than a new dataset.

With the network blocked, the installed package rejected each of these before
any request, with a `QueryError` naming the problem: timezone-naive datetimes
passed directly to the CoastWatch adapter (a crash in v0.12.0), GHCN-Daily
`stations` combined with a `location`, free text passed to NEXRAD, an
eight-day GOES window, and a 32-day NEXRAD window.

The checkout's live tests for CoastWatch, USGS daily values, NEXRAD, GOES,
Storm Events, HURDAT2, and GHCN-Daily were run with explicit live opt-in and
pytest's temporary caches. All twelve passed, with no skips. The USGS listing
now probes one row per page; against the live service a probe past the last
page returned an empty collection, so pagination terminates as designed.

The weather-and-streamflow notebook, which lists USGS pages and GHCN stations,
was executed in a fresh kernel against the live services. It passed without
changes to its saved outputs.

## Limits

This review is a dated upstream-health and first-use snapshot. It covers one
Linux/Python installation, the primary station walkthrough, the adapters
changed in this release, and one notebook. It does not replace the full
scheduled live suite or the offline platform/dependency matrix. Upstream
services can fail or revise files later. Keep manifests, lockfiles, and cached
bytes together; checksums detect changes but do not archive unavailable
upstream revisions.

The earlier [v0.12.0 review](first-use-v0.12.0.md) and
[v0.10.0 review](first-use-v0.10.0.md) retain their original evidence.
