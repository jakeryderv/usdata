# Manifests and reproducible inputs

A manifest declares the datasets needed by a project. Commit it together with
its lockfile. The cache holds the downloaded bytes and should be backed up
separately when historical reproducibility matters.

Start with the [NOAA and USGS example](../../examples/weather-and-streamflow/README.md).
Installation and development setup are in the [README](../../README.md).

## Manifest fields

```yaml
name: weather-and-streamflow
version: "1.0"
sources:
  - dataset: noaa:ghcn-daily
    start: 2024-05-06
    end: 2024-05-07
    variables: [PRCP, TMAX]
    params:
      stations: USW00013967
      units: metric
```

| Field | Meaning |
|---|---|
| `name` | Required project/input-set name. |
| `version` | Manifest format label, default `"1.0"`. Currently informational; use `"1.0"`. It is not the package or dataset version. |
| `sources` | Required, non-empty list of source specifications. |

Each source accepts:

| Field | Meaning |
|---|---|
| `dataset` | Required registry ID, such as `usgs:water-daily`. |
| `location` | A bundled place name or alias. Mutually exclusive with `bbox`. |
| `bbox` | WGS84 box with `west`, `south`, `east`, `north` fields. |
| `start`, `end` | ISO dates or datetimes. All implemented adapters require both. |
| `variables` | List of dataset-specific variable names/codes. Quote numeric codes to retain leading zeros. |
| `params` | Mapping of provider-specific options, listed below. Unknown adapter options are errors. |
| `allow_empty` | Default `false`. Set `true` only if this source is intentionally optional when its query resolves to no assets. |

Unknown manifest and source fields are rejected. `params` must not repeat
`location`, `bbox`, `start`, `end`, or `variables`.

Place lookup currently contains only Oklahoma, Texas, Kansas, California,
Florida, and Colorado (names or postal codes). Their boxes are approximate;
full Census state/county coverage is planned. A bounding box is a rectangle,
so it can include points outside the actual state/county boundary. Antimeridian
crossing is not supported. Prefer explicit station IDs for a small repeatable query.

## Provider options

| Dataset | `params` | Variables and time |
|---|---|---|
| `noaa:ghcn-daily` | `stations`: non-empty comma-separated string or list; otherwise requires a geographic query. `units`: `metric` (default) or `standard`. Explicit stations take precedence over geographic selection. | Names such as `PRCP`, `TMAX`; inclusive calendar dates, time of day ignored. |
| `noaa:nexrad-level2` | `site` or `sites`: radar IDs, mutually exclusive. Alternatively `nearest`: positive integer with a geographic query. Do not combine `nearest` with explicit IDs. | Whole scans, without variable subsetting. UTC timestamps; both interval bounds included. A date-only end means midnight at the start of that day. |
| `usgs:water-daily` | `site` or `sites`: quoted monitoring IDs, mutually exclusive. Alternatively a geographic query. `statistic_id`: quoted five-digit code, default `"00003"` (daily mean). Explicit sites and a geographic filter both apply when present. | Quoted parameter codes such as `"00060"`; inclusive local calendar dates, time of day ignored. |

Station/site options accept strings or lists of strings. NOAA radar IDs are
case-insensitive. USGS IDs may include the `USGS-` prefix. Empty explicit lists
are invalid even with `allow_empty: true`; that flag permits an empty result
from a valid query.

See [NOAA](../providers/noaa.md) and [USGS](../providers/usgs.md) for source
behavior, units, limitations, and endpoint details.

## Pull, refresh, and restore

```sh
usdata pull dataset.yaml --cache-dir .data
usdata verify dataset.yaml --cache-dir .data
```

The first pull resolves each source, downloads missing assets, and writes
`dataset.lock.json`. Every required source must resolve to at least one asset;
otherwise pull exits 1 and does not create or replace the lockfile. Files
successfully fetched before the failure remain cached for the next attempt.
This checks asset presence, not completeness of all scientific observations
inside a returned file.

With a lockfile present, pull restores the pinned assets without re-querying
listings. Cached bytes must match their pinned checksums; missing or altered
files are downloaded again. If upstream now returns different bytes, restoration
fails with a checksum mismatch and preserves any existing file at that path.

If the manifest changes, both pull and verify refuse it with exit code 2:

```sh
usdata pull dataset.yaml --cache-dir .data --force
```

For **pull**, `--force` re-resolves queries and replaces the lockfile after all
required sources succeed. Valid cached responses may still be reused. For
**fetch**, `--force` means re-download even a valid cached file. These flags
have different purposes; re-locking is not a guarantee of upstream freshness.

The manifest checksum covers its exact bytes. Editing whitespace or comments
also requires re-locking. An intentionally empty optional source is pinned as
no assets; restore does not search for newly available results. Use `pull --force`
to resolve it again.

## What verification guarantees

`verify` is offline. It checks that the manifest matches the lockfile, then
hashes the cached files. It exits 1 if a file is missing or has changed, 2 for
an invalid/mismatched manifest or unreadable lockfile, and 0 when checks pass.
It does not query upstream or validate the scientific meaning of the data.
An older empty lockfile cannot prove that all original queries were satisfied;
re-resolve it using the current empty-source policy.

Lockfiles contain the manifest checksum, generation time, usdata version,
resolved asset URLs, file checksums, and provenance. Sidecars record source URL,
provider, dataset, retrieval time, byte count, checksum, and license.

**A lockfile detects changed data; it does not archive data.** Query-based APIs
may revise observations or page ordering and may not expose historical
versions. If both the cached bytes and their upstream version are gone, usdata
cannot recreate them. Preserve the cache alongside the manifest and lockfile
for long-lived work. The cache stores one current file per asset ID; it is not
a versioned archive.

## Failures and retries

GET requests retry transient connection, timeout, and remote protocol failures,
as well as HTTP 429, 500, 502, 503, and 504, for at most three attempts. Default
backoff is 0.5 then 1 second. `Retry-After` seconds and HTTP dates are respected;
a requested wait over 30 seconds is surfaced as an error instead of retried early.
Interrupted downloads restart from the beginning in a temporary file. Permanent
HTTP errors, local filesystem failures, and checksum mismatches are not retried.

CLI exit codes: 0 success; 1 no assets or verification drift; 2 invalid input;
3 unimplemented dataset; 4 upstream or checksum failure. Unit tests prohibit
network connections; integration tests exercise the live services separately.
