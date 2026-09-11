---
template: home.html
hide:
  - toc
  - navigation
---

# Public science. Reproducible inputs.

Discover U.S. scientific datasets, fetch their files, and keep the evidence behind
your analysis. One Python SDK and CLI for supported NOAA and USGS data.

[Start with one dataset](index.md){ .md-button .md-button--primary }
[Explore the catalog](generated/catalog/index.md){ .md-button }

```sh
python -m pip install usdata
usdata search precipitation --location Oklahoma
usdata info noaa:ghcn-daily
```

<div class="grid cards" markdown>

-   **Find your source**

    ---

    Browse supported datasets with explicit formats, selection rules, and practical examples.

    [Browse datasets](generated/catalog/index.md)

-   **Fetch and analyze**

    ---

    Download source files and open them locally with optional CSV, radar, and NetCDF readers.

    [Follow the guide](guides/fetch-and-analyze.md)

-   **Keep the evidence**

    ---

    Record queries, provenance, and checksums. Lock, restore, and verify your analysis inputs.

    [Use a manifest](reference/manifests.md)

</div>

## See it in practice

Explore [weather and streamflow](../examples/weather-and-streamflow/example.ipynb),
[satellite imagery](../examples/goes-imagery/example.ipynb), or
[coastal water levels](../examples/coastal-water-levels/README.md).
The [example collection](../examples/README.md) includes saved outputs and runnable notebooks.

**Pre-alpha.** This site follows the current source checkout. Features marked
**Unreleased** require a source installation; the [changelog](../CHANGELOG.md)
records published versions.
