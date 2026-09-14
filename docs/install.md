# Install

usdata needs Python 3.11 or newer. The core package depends only on pydantic,
PyYAML, Typer, and httpx. Readers for each file format are optional extras so
that fetching and pinning never pull in a scientific stack you do not use.

```sh
python -m pip install "usdata[pandas]"
```

| Extra | Installs | Opens |
| --- | --- | --- |
| `pandas` | pandas | CSV, gzip CSV, ERDDAP CSV, HURDAT2 text, SPC and Storm Events tables |
| `radar` | xradar | NEXRAD Level II volumes |
| `netcdf` | xarray, h5netcdf | GOES ABI scenes and GLM detection files |
| `grib` | ecCodes, xarray | MRMS, HRRR, and GFS GRIB2 fields |

Combine extras as needed: `pip install "usdata[pandas,grib]"`. Without an extra,
`fetch` and `pull` still work and `open()` reports which extra to install.

The `grib` extra installs with pip alone on Linux for every supported Python and
on Windows for CPython 3.13 and earlier. On macOS, and on Windows with Python
3.14, install the ecCodes library first from conda-forge or Homebrew
(`brew install eccodes`); the reader then finds it and says so if it cannot.
See [readers and their limits](reference/readers.md) for what each reader
returns.

## Source installation

These docs describe the current source checkout. A feature marked
**Unreleased** or **since** a version newer than the one on PyPI needs the
checkout. Install it with [uv](https://docs.astral.sh/uv/):

```sh
git clone https://github.com/jakeryderv/usdata && cd usdata
uv sync --extra pandas
uv run usdata info noaa:coops-water-levels
```

Run source examples from this checkout with `uv run usdata` (CLI) or
`uv run python` (Python), adding `--extra radar`, `--extra netcdf`, or
`--extra grib` for those formats. Contributor setup and commands are in the
[repository README](https://github.com/jakeryderv/usdata#development).
