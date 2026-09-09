# Runnable notebooks

These notebooks are the primary examples for usdata. Open them on GitHub to read
the saved outputs, or run them locally to change queries and inspect the results.

| Notebook | Demonstrates |
|---|---|
| [Weather and streamflow](weather-and-streamflow/example.ipynb) | NOAA/USGS inputs, manifests, provenance, cache reuse, verification, and locked restoration |
| [Sea-surface temperature](sst-analysis/example.ipynb) | A four-cell CoastWatch subset, pandas opening, ERDDAP units, and a spatial plot |
| [Monthly climate](monthly-climate/example.ipynb) | GSOM monthly observations, whole-month selection, a two-panel plot, and manifest verification |
| [Storm Events](storm-events/example.ipynb) | Annual gzip CSV, local Oklahoma/date filtering, report counts, damage ratings, and source verification (available since v0.8) |
| [Radar reflectivity](radar-reflectivity/example.ipynb) | One NEXRAD volume, xradar sweeps, field units, reflectivity plot, and provenance |
| [GOES infrared imagery](goes-imagery/example.ipynb) | NetCDF4 opening, CF decoding, quality flags, scan coordinates and brightness-temperature imagery |
| [Event context](event-context/example.ipynb) | One Storm Events report matched to NEXRAD and GOES, explicit UTC conversion, safe radar sweep selection, projected context, and locked restoration (Unreleased) |

## Run interactively

From the repository root, with [uv and just installed](../README.md#development):

```sh
just notebooks
```

This launches JupyterLab with the optional `examples` dependency group, which
includes pandas, plotting, and notebook tools. The commands also install the
optional `radar` and `netcdf` extras. Notebook tools are development dependencies;
installing base `usdata` does not install them or the scientific reader extras. Select a notebook and use the Python 3
kernel. In an IDE, select this checkout's `.venv` interpreter after the environment
has been installed. Use **Restart Kernel and Run All Cells** to check that a notebook
works without hidden state. Each notebook works from its own folder or the repo root.

The first run needs access to NOAA and/or USGS. Interactive runs use the normal
usdata cache (`USDATA_CACHE_DIR` overrides it). The manifest examples retain
their `dataset.yaml` files; a first pull creates an ignored `dataset.lock.json`
beside the manifest. When changing a locked manifest deliberately, use
`pull(manifest, force=True)` to resolve and lock the new inputs.

## Validate or refresh saved outputs

```sh
just check-notebooks        # offline checks of committed notebook outputs
just run-notebooks          # live execution, without changing committed outputs
just run-notebooks --write  # live execution, then save all successful results
```

The runner starts each notebook in a fresh kernel with temporary manifests,
lockfiles, and caches. It uses the same interpreter as the examples environment;
it does not install a global kernel. A failure leaves the committed notebooks
untouched. The scheduled Integration workflow runs the live notebook check
separately from the existing adapter tests. Regular `just check` validates the
saved notebooks offline.

Saved outputs are snapshots, not promises about future upstream responses. Each
notebook records its execution time, package versions, source retrieval times,
source URLs, and full input checksums. Preserve both the manifest and lockfile in
your own analysis project, and keep cached bytes for long-lived reproducibility.

Commit compact executed outputs: short tables, small static plots, and relevant
provenance. The runner removes execution timing and widget metadata while keeping
the visible outputs. Review the notebook diff before committing a refresh;
upstream revisions can change both observations and checksums. The notebooks are
the tutorial source; equivalent analysis scripts are not maintained alongside them.
