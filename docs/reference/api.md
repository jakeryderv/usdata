# Python API

Signatures and descriptions below are generated from Python source at build time.
This reference covers the public workflow and the objects it returns; internal
transports and provider implementation helpers are intentionally omitted.
See [fetch and analyze](../guides/fetch-and-analyze.md) for complete workflows.

## Discovery and queries

::: usdata.search
::: usdata.get
::: usdata.build_query
::: usdata.Registry
    options:
      members: [bundled, from_yaml, search, get, providers, domains]

## Fetching and opening

::: usdata.fetch.fetch
::: usdata.fetch.FetchedAsset
    options:
      members: [asset, path, provenance, from_cache, open]

## Reproducible inputs

::: usdata.pull.pull
::: usdata.pull.verify
::: usdata.pull.PullResult
::: usdata.pull.Drift
::: usdata.manifest.Manifest
::: usdata.manifest.SourceSpec
::: usdata.manifest.Lockfile
::: usdata.manifest.LockedAsset

## Temporal selection

::: usdata.select_by_time
::: usdata.TemporalSelection

## Shared types

::: usdata.Asset
::: usdata.BBox
::: usdata.TimeRange
::: usdata.Dataset
::: usdata.Query
::: usdata.Provenance
::: usdata.SearchResult
