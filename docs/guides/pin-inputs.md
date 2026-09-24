# Pin inputs for a paper

A manifest names the queries an analysis depends on. A lockfile pins the exact
bytes they produced. With both committed and the cache backed up, anyone can
repeat the download and prove the inputs match.

```yaml
name: weather-and-streamflow
sources:
  - dataset: noaa:ghcn-daily
    start: 2024-05-06
    end: 2024-05-07
    variables: [PRCP, TMAX]
    params:
      stations: USW00013967
  - dataset: usgs:water-daily
    start: 2024-05-06
    end: 2024-05-07
    variables: ["00060"]
    params:
      sites: "07164500"
```

```sh
usdata pull dataset.yaml --cache-dir .data     # resolves, downloads, writes dataset.lock.json
usdata verify dataset.yaml --cache-dir .data   # offline: manifest checksum and every file
```

The first pull writes the lockfile. Later pulls restore from it without
repeating discovery. Verify never touches the network. Pull prints one
tab-separated line per asset and a summary line on stderr; `--quiet` keeps the
summary and drops the per-asset lines, and `--no-progress` turns off the
terminal progress display without changing either.

## Restore on another machine

Copy the manifest and lockfile, then run the same pull into an empty
directory. Missing files are downloaded from their pinned URLs and checked
against their pins:

```sh
usdata pull dataset.yaml --cache-dir fresh && usdata verify dataset.yaml --cache-dir fresh
```

## What to commit and what to back up

Commit `dataset.yaml` and `dataset.lock.json`. Back up the cache directory
separately for anything that must be reproducible years later: a checksum
proves bytes are unchanged, but cannot recover bytes an agency no longer
serves. The archive-backed [examples](https://usdata.dev/examples/) commit
their lockfiles and are restored from them every week, so each example page
has a lockfile to download alongside its manifest.

## When pull exits 4

The agency revised a file behind a pinned URL. Pull restores everything that
still matches, lists every asset that changed, and leaves the lockfile alone.
Decide per entry:

```sh
usdata pull dataset.yaml --cache-dir .data --update noaa:ghcn-daily
```

That accepts the new bytes for that dataset only and rewrites only its pin.
Use `--force` instead when the manifest itself changed or you want every
source re-resolved. To keep the old bytes instead, a mirror that stores files
by checksum can serve them: `USDATA_MIRROR_URL` names one, and the shipped
examples restore from the project's at `https://data.usdata.dev`. The full
contract is in [provenance and drift](../concepts/provenance-and-drift.md).

A dataset that needs a key reads it from environment variables that `usdata
info` names, so a manifest and lockfile never hold one and can be shared as
they are. Someone without a key can still restore what the cache or a mirror
holds.

--8<-- "_snippets/upstream-revisions.md"

The [weather and streamflow example](https://usdata.dev/examples/weather-and-streamflow/)
runs this whole loop, including restoring into an empty cache, and keeps its
lockfile with the notebook.
