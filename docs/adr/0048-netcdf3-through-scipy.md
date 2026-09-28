# 0048: NetCDF3 files open through scipy, and CF calendars through cftime

Status: accepted. Date: 2026-09-28. Extends [ADR 0009](0009-eager-local-netcdf4-reader.md).

## Context

The netcdf extra reads NetCDF4 only: ADR 0009 chose h5netcdf, which reads
HDF5, and left classic NetCDF3 to xarray on the file path. Every NetCDF dataset
in the catalog until now was NetCDF4. ERSST v5
([issue 390](https://github.com/jakeryderv/usdata/issues/390)) is not. Its
monthly files from January 1854 to December 2007 begin `CDF\x01`, classic
NetCDF3, and only those from January 2008 onward begin `\x89HDF`. The same
older files state time as `minutes since <month start>` on a `360_day`
calendar, which xarray decodes only with cftime. One dataset therefore needs
two formats and a non-standard calendar across a single time series.

## Decision

The netcdf extra adds scipy and cftime. `open_netcdf` and `inspect` read a
file's first four bytes: `CDF\x01` or `CDF\x02`, classic or 64-bit offset
NetCDF3, opens with xarray's `scipy` engine, and anything else opens with
`h5netcdf` as before. The choice follows the bytes rather than the name or
media type, which say `.nc` and `application/x-netcdf` for both. Both engines
read from a local file object, so neither can be handed a URL. A time
coordinate on a non-standard calendar decodes to cftime dates, which is
xarray's own behaviour once cftime is installed. The reader does not convert
them to `datetime64`: a 360-day date has no faithful standard equivalent.

Only the engine a file needs is imported. A NetCDF4 file opens without scipy,
and a NetCDF3 file without h5netcdf, so an environment built before this change
keeps reading what it read. A missing module is still the one
`MissingReaderDependency` naming the extra.

## Alternatives

- **netCDF4-python.** It reads every format through the Unidata C library, and
  would replace both h5netcdf and scipy. But it ties the extra to that
  library's wheel, the same kind of binary dependency that leaves the grib
  extra unverified on macOS. scipy and cftime publish wheels for every
  platform and Python version the package supports.
- **Decode times without cftime** (`decode_times=False` for non-standard
  calendars). A caller would get raw minutes and have to know the calendar,
  which is decoding the reader exists to do.
- **Leave NetCDF3 to the caller.** ERSST is the first case but not the last:
  the planned NetCDF climate data records include classic files as well.

## Consequences

The netcdf extra grows by scipy (about 83 MB installed on Linux) and cftime (about 7 MB), a real cost for one file format that only the extra pays.
`usdata doctor` checks both. Concatenating ERSST months across 2007 and 2008
meets two time representations, cftime 360-day month starts and `datetime64`
mid-month stamps. That belongs to the dataset, and its guide says so rather
than the reader hiding it.
