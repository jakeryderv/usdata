# Python API

Signatures and descriptions below are generated from Python source at build time.
This reference covers the public workflow and the objects it returns; internal
transports and provider implementation helpers are intentionally omitted.
Every public function that takes a filesystem path accepts a `str` or any
`os.PathLike[str]` and coerces it once on entry, so a path `usdata inspect`
printed can be pasted straight back in.
See [fetch and analyze](../guides/fetch-and-analyze.md) for complete workflows.

## Discovery and queries

::: usdata.datasets
::: usdata.search
::: usdata.get
::: usdata.build_query
::: usdata.Registry
    options:
      members: [bundled, from_yaml, list, search, get, providers, domains]

## Fetching and opening

::: usdata.fetch
::: usdata.fetch_asset
::: usdata.FetchedAsset
    options:
      members: [asset, path, provenance, from_cache, open, inspect]

## Inspecting a file

::: usdata.inspect_asset
::: usdata.inspect_path
::: usdata.inspect.Summary
::: usdata.inspect.CsvSummary
::: usdata.inspect.NetcdfSummary
::: usdata.inspect.NetcdfVariable
::: usdata.inspect.Grib2Summary
::: usdata.inspect.GribMessage

## Reproducible inputs

::: usdata.pull.pull
::: usdata.pull.plan
::: usdata.pull.verify
::: usdata.pull.PullResult
::: usdata.pull.Plan
::: usdata.pull.SourcePlan
::: usdata.pull.Drift
::: usdata.manifest.Manifest
::: usdata.manifest.SourceSpec
::: usdata.manifest.Lockfile
::: usdata.manifest.LockedAsset

## Citations

::: usdata.cite_dataset
::: usdata.cite_lockfile
::: usdata.Citation
    options:
      members: [as_text, as_bibtex]

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
