# First-use review: v0.10.0

Review for [issue #72](https://github.com/jakeryderv/usdata/issues/72), observed
on 2026-09-10 UTC. The primary walkthrough passed with the published package.
Both follow-on Python examples initially failed because they passed strings to
the manifest API; corrected `pathlib.Path` examples passed on the same release.
No runtime changes were needed.

## Environment and method

- PyPI `usdata==0.10.0`, installed with the pandas extra in a new virtual
  environment outside the repository; no editable installation or existing cache.
- CPython 3.14.7, Linux x86_64, kernel `7.1.5-76070105-generic`, glibc 2.39;
  pip 26.2.1, pandas 3.0.5, NumPy 2.5.3, Pydantic 2.13.5, HTTPX 0.28.1,
  PyYAML 6.0.3, Typer 0.27.2.
- Documentation baseline: main commit
  `b74bd0347c57afe179639880476ea2ad01f97e45`.
- Installed using `python -m pip install --index-url https://pypi.org/simple
  "usdata[pandas]"`. The imported package was under the temporary environment's
  `site-packages/usdata`, not the checkout.
- Set `USDATA_CACHE_DIR` to an empty temporary directory, preserving the user's
  normal cache. Used additional empty directories for restoration and corrected
  examples. Downloaded bytes, manifests, lockfiles, and raw command logs stayed
  outside Git.
- Ran maintained Python snippets as written before editing them, and extracted
  the corrected snippets again for the rerun. Recorded exit codes and outputs.
- For offline verification and local-reading probes, replaced DNS lookup and
  socket connection functions with guards that raise on network access.
  Downloads ran separately with network access. A second fresh core-only
  installation supplied the missing-reader probe.

## Walkthrough results

The [first-use walkthrough](../index.md) used station `USW00013967`, inclusive
dates May 6–7, 2024, and variables `PRCP,TMAX`.

| Step | Command or operation | Result |
|---|---|---|
| Discover | `usdata search precipitation --location Oklahoma` | Exit 0; GHCN-Daily ranked first, followed by GSOM, GSOY, and NEXRAD. |
| Inspect | `usdata info noaa:ghcn-daily` | Exit 0; available status, source, temporal/variable capabilities, and coverage shown. |
| Fetch | `usdata fetch noaa:ghcn-daily -p stations=USW00013967 --start 2024-05-06 --end 2024-05-07 --vars PRCP,TMAX` | Exit 0; one 209-byte CSV. |
| Read | Walkthrough Python snippet: `fetch(...)`, then `items[0].open()` | Exit 0; two rows with station/date identifiers and precipitation/temperature columns. |
| Lock | `usdata pull dataset.yaml` using the walkthrough manifest | Exit 0; reused the verified cached asset and wrote `dataset.lock.json`. |
| Verify | `usdata verify dataset.yaml` | Exit 0; all assets match. |
| Restore | `usdata pull dataset.yaml --cache-dir restored-data`, initially empty | Exit 0; downloaded the pinned 209-byte asset and reported restoration from the existing lockfile. |
| Verify restored | `usdata verify dataset.yaml --cache-dir restored-data` with network guards | Exit 0; all assets match. |
| Read locally | Reconstruct the fetched asset from the lockfile and cache, then call `open()` with network guards | Exit 0; original rows and provenance available without fetching. |

Observed daily rows: May 6 had `PRCP=10.9`, `TMAX=27.2`; May 7 had `PRCP=0.0`,
`TMAX=26.7` in the requested metric units. The CSV reader retained the station
identifier as text and exposed the source URL, retrieval time, checksum, size,
license, dataset, and package version in `frame.attrs["usdata"]`.

## Follow-on examples and corrections

Both CLI manifest pulls and offline verification passed before any edits.
Both original Python snippets failed with
`AttributeError: 'str' object has no attribute 'with_suffix'`.
The existing SDK requires `Path`; the examples incorrectly supplied strings.

Corrections use `Path("dataset.yaml")`, show installation from PyPI with the
pandas extra, and run relative to the directory containing the downloaded
manifest. Source-checkout instructions remain as an alternative. The manifest
reference now explains the SDK path requirement. The main walkthrough names the
Python/environment prerequisite and demonstrates a fresh-cache restore.

For each corrected example, saved its unchanged manifest into a new working
directory, ran the following commands with a new temporary cache, then executed
the maintained Python snippet with network guards:

```sh
python -m pip install "usdata[pandas]"
usdata pull dataset.yaml
usdata verify dataset.yaml
python example.py
```

Here `example.py` contains the Python block from the corresponding guide.

| Example | Corrected result |
|---|---|
| [Annual climate](../../examples/annual-climate/README.md) | All steps exited 0; one 133-byte CSV and one 2024 row for `USW00013967`, with `PRCP=942.4` and `TAVG=17.4`. `DATE` remained a string. |
| [Coastal water levels](../../examples/coastal-water-levels/README.md) | All steps exited 0; one 186-byte CSV with UTC observations at 00:00, 00:06, and 00:12 on May 6, 2024. Water levels were 1.765, 1.730, and 1.702 meters; all three quality values were `v`. |

The guides explain complete UTC-year selection for GSOY and the CO-OPS station,
datum, minute precision, 28-day limit, quality fields, and lack of gap filling.
The coastal example's local column renaming and UTC conversion preserved the
cached bytes; the source URL retained station `8518750`, datum `MLLW`, metric
units, and `time_zone=gmt`.

## Common mistakes

| Probe | Observed behavior | Assessment |
|---|---|---|
| Open the cached GHCN CSV in the core-only environment | `MissingReaderDependency` names pandas and gives `pip install "usdata[pandas]"` and `uv add` remedies. | Expected failure with actionable guidance. |
| `usdata fetch noaa:coops-water-levels --start 2024-05-06T00:00Z --end 2024-05-06T00:12Z -p datum=MLLW` | Exit 2: `station must be a seven-digit string, for example '8518750'`. | Expected failure identifying the missing selector. |
| Add a comment to a copy of the locked manifest, then verify that copy | Exit 2: manifest changed since the lockfile was written; pull with force to re-resolve. | Expected failure; exact-byte manifest checks and intentional re-locking are explained in the reference. |

## Limits and next work

These are observed snapshots, not guarantees about future upstream availability.
The original and restored GHCN bytes matched, and no upstream revision or outage
blocked this review. Preserve the cache with the manifest and lockfile: a checksum
does not archive an upstream version. Verification does not establish scientific
correctness or completeness.

This review covered three bounded workflows on one Linux/Python configuration.
It did not repeat the full platform matrix, exercise every dataset or optional
decoder, or refresh notebooks. Existing CI covers the supported package profiles
and installed-wheel platforms; it is separate from this live usability review.

No larger behavioral follow-up was identified in this scope. The next selected
work is [documentation publishing (#56)](https://github.com/jakeryderv/usdata/issues/56),
which should include the corrected guides. A dataset expansion remains a candidate
to scope around a concrete analysis need, not an automatic consequence of finishing
this review.
