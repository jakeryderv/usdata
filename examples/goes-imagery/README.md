# GOES infrared scene

Open [example.ipynb](example.ipynb) to see an executed GOES-18 channel-13 scene,
quality-filtered brightness-temperature image in scan coordinates, and pixel
histogram. Available from source for v0.8.

Use [notebook setup](../README.md) from the repository root. The NetCDF reader
requires `usdata[netcdf]`; the example environment supplies plotting and Jupyter.
The repository pins Python 3.14.7 to avoid an upstream crash in older Linux uv
Python 3.14 builds. Other supported Python versions can also run the notebook.

The manifest requests one exact scan start, 2024-05-06T12:01:18.1Z, with explicit
satellite 18, channel 13, and product ABI-L2-CMIPC. The archive file is ~3.8 MB;
decoding uses additional memory. The notebook preserves the full input checksum,
source URL and retrieval time, verifies the manifest lockfile, and demonstrates
cache reuse. Raw scene bytes and provenance remain unchanged.

`CMI` is infrared brightness temperature in kelvin; `DQF == 0` is selected
explicitly by this analysis. It is not a surface-air-temperature estimate. The
plot uses geostationary scan angles rather than latitude/longitude. The reader
preserves projection metadata but does not reproject the image. Plot sampling
reduces output size; summaries use all accepted finite pixels.
