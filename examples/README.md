# Runnable notebooks

Browse [examples by question](https://usdata.dev/examples/) to read the saved
outputs and inspect the source datasets. The notebooks and manifests in this
directory are the maintained sources; run them locally to change queries and
inspect the results. The website renders saved content without running analyses.

| Notebook | Demonstrates |
|---|---|
| [Weather and streamflow](https://usdata.dev/examples/weather-and-streamflow/) | NOAA/USGS inputs, manifests, provenance, cache reuse, verification, and locked restoration |
| [Sea-surface temperature](https://usdata.dev/examples/sst-analysis/) | A four-cell CoastWatch subset, pandas opening, ERDDAP units, and a spatial plot |
| [Monthly climate](https://usdata.dev/examples/monthly-climate/) | GSOM monthly observations, whole-month selection, a two-panel plot, and manifest verification |
| [Climate anomalies](https://usdata.dev/examples/climate-anomalies/) | GSOM observations against 1991-2020 normals, month alignment, an upstream unit exception, anomaly plots, and stale-lockfile guidance (available since v0.12.0) |
| [Storm surge](https://usdata.dev/examples/storm-surge/) | CO-OPS observed water levels minus tide predictions across Hurricane Helene's landfall, the peak residual, and its timing against the HURDAT2 track (available since v0.14.0) |
| [Storm Events](https://usdata.dev/examples/storm-events/) | Annual gzip CSV, local Oklahoma/date filtering, report counts, damage ratings, and source verification (available since v0.8) |
| [Radar reflectivity](https://usdata.dev/examples/radar-reflectivity/) | One NEXRAD volume, xradar sweeps, field units, reflectivity plot, and provenance |
| [GOES infrared imagery](https://usdata.dev/examples/goes-imagery/) | NetCDF4 opening, CF decoding, quality flags, scan coordinates and brightness-temperature imagery |
| [Event context](https://usdata.dev/examples/event-context/) | One Storm Events report matched to NEXRAD and GOES, explicit UTC conversion, safe radar sweep selection, projected context, and locked restoration (available since v0.9) |

## Manifest examples

[Annual airport climate](https://usdata.dev/examples/annual-climate/) demonstrates GSOY annual
selection and local CSV opening with a small manifest (available since v0.10.0).

[Monthly climate normals](https://usdata.dev/examples/climate-normals/) requests 1991-2020 monthly
temperature and precipitation normals for the same airport and compares one
observed month against them (available since v0.11.0).

[Hourly airport observations](https://usdata.dev/examples/hourly-observations/) pulls three
days of Local Climatological Data for one airport and checks the hourly
readings against NCEI's daily summary (available since v0.14.0).

[Atlantic hurricane best tracks](https://usdata.dev/examples/hurdat2/) fetches the whole HURDAT2
Atlantic file and reads it into one row per track point (available since v0.12.0).

## Run interactively

From the repository root, with [uv and just installed](https://docs.usdata.dev/project/#development):

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

A small [coastal water-level manifest](https://usdata.dev/examples/coastal-water-levels/) demonstrates CO-OPS datum, units, quality flags, and local CSV reading (available since v0.10.0).
