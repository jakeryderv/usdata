# First-use review: v0.12.0

Observed on 2026-09-12 UTC against the published `usdata[pandas]==0.12.0`
package and the maintained [getting-started walkthrough](../index.md).
The walkthrough, five newest-dataset live checks, and refreshed
[climate-anomalies notebook](../examples/climate-anomalies/example.md) passed.
No SDK or adapter changes were needed.

## Method and results

The published package was installed into a new temporary virtual environment
outside the repository on Linux with Python 3.14.7. The imported package came
from that environment's `site-packages`, with no editable installation.
The walkthrough used fresh, isolated temporary cache directories; user caches
were untouched. The Python and manifest blocks were extracted from the maintained
guide. The release baseline was `bc785de` (v0.12.0).

| Step | Observed result |
| --- | --- |
| Search precipitation in Oklahoma | Completed successfully; supported station and other weather datasets returned. |
| Inspect `noaa:ghcn-daily` | Dataset information and accepted parameters displayed successfully. |
| Fetch station `USW00013967`, May 6–7, 2024, `PRCP,TMAX` | One 209-byte CSV downloaded. |
| Execute the guide's Python reading example | Two observation rows opened successfully. |
| Pull and verify the guide's manifest | Lockfile written; all cached assets matched. |
| Restore into a second empty cache | Pinned source downloaded again; restored bytes passed verification. |
| Read and verify the restored inputs with DNS and socket connections blocked | Both succeeded without network access. |

## Newest-dataset checks

The checkout's bounded live tests were run with explicit live opt-in and pytest's
temporary caches. All five passed, with no skips:

- Climate normals: airport station discovery; a daily February 27–March 1
  window including leap day; all twelve monthly rows and exact-byte restoration.
- HURDAT2: download and parse the current whole Atlantic file; infer the local
  reader and verify Hurricane Ida's identity, coordinate signs, and peak wind.

The climate-anomalies notebook was executed in a fresh kernel and temporary
working directory with isolated inputs. Its saved outputs were refreshed only
after successful execution. It downloaded both sources, aligned twelve months,
handled the documented temperature-unit exception, produced both plots, verified
the lockfile, and confirmed a subsequent pull reused the verified cache.

The calculated summary reported 10 warmer-than-normal months and 942.4 mm of
2024 precipitation against 924.3 mm of summed monthly normals, a +18.1 mm
difference. These are observations from one station and one execution, not a
regional estimate, climate trend, or statistical significance test.

## Limits

This review is a dated upstream-health and first-use snapshot. It covers one
Linux/Python installation, the primary station walkthrough, climate normals,
Atlantic HURDAT2, and the climate example. It does not replace the full scheduled
live suite or the offline platform/dependency matrix. Upstream services can fail
or revise files later. Keep manifests, lockfiles, and cached bytes together;
checksums detect changes but do not archive unavailable upstream revisions.

The earlier [v0.10.0 review](first-use-v0.10.0.md) retains its original evidence
and example corrections.
