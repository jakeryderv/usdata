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

## Check your environment

`usdata doctor` reports what it finds and fixes nothing: the interpreter, this
install, each reader extra with its versions, the ecCodes library behind the
`grib` extra, the cache directory with its free space, any
`USDATA_CACHE_DIR`, `XDG_CACHE_HOME`, or `USDATA_MIRROR_URL` setting, and, for
each dataset that needs a key, whether its variables are set. It never prints a
key.

```console
$ usdata doctor
python        ok    3.13.7 (CPython) at /home/ada/.venvs/usdata/bin/python3
platform      ok    Linux-6.8.0-x86_64-with-glibc2.39 on x86_64
usdata        ok    0.16.0 from /home/ada/.venvs/usdata/lib/python3.13/site-packages/usdata
extra:pandas  ok    pandas 2.3.1
extra:grib    warn  not usable (No module named 'eccodes'); install: pip install "usdata[grib]"
cache         ok    /home/ada/.cache/usdata: exists, writable, 91.4 GiB free
```

A missing extra is a warning: the core still fetches and pins. The command exits
1 only when something is broken, such as a cache directory it cannot write. Add
`--network` for one short request per upstream host family, and `--json` for the
same report as a JSON object.

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
