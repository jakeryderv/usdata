# Fetch, open, and summarize SST

Open the [executed notebook](example.ipynb) to inspect four CoastWatch ocean grid
centers, their units and provenance, a small spatial plot, and cache reuse.
See [examples setup](../README.md) to run it interactively or refresh its outputs.

Requires usdata v0.6 or newer. The sample is at 2024-05-06T12:00Z. Its mean is an
unweighted average of four nearby grid centers, not a regional climate statistic.
ERDDAP's units row becomes metadata rather than an observation; raw bytes and
provenance remain intact when the DataFrame is edited.

Saved results include execution and retrieval times plus checksums; NOAA can revise
the underlying data. The [reader reference](../../docs/content/reference/readers.md)
explains opening options and the limits of in-memory metadata.
