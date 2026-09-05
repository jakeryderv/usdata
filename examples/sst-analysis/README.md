# Fetch, open, and summarize SST

Available from source for v0.6. Follow [development setup](../../README.md#development),
then run from the repository root:

```sh
uv run --extra pandas python examples/sst-analysis/analyze.py
```

This downloads a tiny CoastWatch SST subset: four nearby ocean grid centers at
2024-05-06T12:00Z. It opens the CSV as a DataFrame, parses timestamps, and prints
the mean temperature in the units supplied by the source, plus its checksum.
It needs live NOAA access for the first fetch; valid cached bytes are reused.

The ERDDAP units row becomes metadata, not an observation. The example computes
an unweighted mean of these four grid centers, not a regional climate statistic.
Downloaded bytes and provenance stay intact when the DataFrame is opened or edited.
The [reader reference](../../docs/reference/readers.md) documents other options
and the limits of in-memory metadata.
