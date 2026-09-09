# Packed NetCDF4 test grid

`packed-grid.nc` is an actual HDF5/NetCDF4 fixture generated locally with
h5netcdf 1.8.1. It contains a 2×3 synthetic CF grid, not NOAA observations:

- `x` / `y`: scan coordinates in radians.
- `CMI`: signed int16 storage with `_Unsigned=true`, `_FillValue=-1`,
  `scale_factor=0.5`, `add_offset=250`, and units K.
- Stored CMI values: `[[0, 10, -1], [20, 30, 40]]`; expected decoded values:
  `[[250, 255, NaN], [260, 265, 270]]` K.
- `DQF`: `[[0, 1, 3], [0, 0, 0]]`, with good/conditional/missing flag metadata.

- `unsigned_count`: int16 `[0, -32768, -1]` with `_Unsigned=true` and fill -1;
  decodes to `[0, 32768, NaN]`, testing the stored high bit.
- `t`: scalar CF time, 0 seconds since 2024-05-06 12:01:18.1.

This fixture tests real backend decoding, masking, scaling, coordinate/units
retention, and closed-file resource ownership without network access. Live GOES
scenes and the executed satellite notebook independently verify source data.
