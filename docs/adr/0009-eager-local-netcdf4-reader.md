# 0009: Eager local NetCDF4 reading with xarray

Status: accepted. Date: 2026-09-08.

## Context

The GOES ABI adapter fetches complete NetCDF4/HDF5 scenes. A local reader must
preserve CF scaling, missing values, dimensions, units, projection attributes,
and quality flags without introducing scientific dependencies into core or
leaving an open file handle whose ownership is unclear.

## Decision

Add `reader="netcdf"` and infer it from NetCDF media types. The `netcdf` extra
installs xarray and h5netcdf with its explicit h5py backend. Pass an already-open
local binary file to the fixed `h5netcdf` engine, load the root Dataset eagerly,
and close both dataset and file before returning. Dataset attributes receive a
copy of asset ID and provenance under `usdata`, matching the reader metadata
convention. CSV-only options are rejected for this reader.

The initial scope is NetCDF4/HDF5 root datasets, demonstrated by GOES scenes.
Classic NetCDF3, arbitrary HDF5, nested-group traversal, lazy/dask opening,
remote URLs, spatial reprojection and scientific quality filtering are excluded.
Callers can use `fetched.path` with another backend for those needs. Eager loading
is appropriate for the bounded example but requires memory for the decoded scene.

## Validation and runtime

A real synthetic NetCDF4 fixture tests packed/unsigned values, fill masking,
CF time, coordinate and unit retention, and closure. Live satellite execution
independently checks a 1500-by-2500 C13 scene with source quality flags.

A Linux python-build-standalone 3.14.3 interpreter crashed in NumPy temporary
elision during CF masking, independently reproduced with a plain boolean-array
operation. Changing NumPy or the NetCDF engine did not help. This matches
[upstream issue 991](https://github.com/astral-sh/python-build-standalone/issues/991),
fixed in newer interpreter builds. The same scene succeeds with Python 3.11 and
3.14.7. Pin development `.python-version` to 3.14.7 so notebook setup obtains the
verified runtime; package support remains Python >=3.11, with no NumPy version cap.

## Consequences

Reading uses no network, writes no cache/sidecar bytes, and remains independent
of the current registry. Metadata can be discarded by downstream processing;
manifest lockfiles and sidecars remain the durable source record. Tests and
installed-wheel checks include core and NetCDF profiles, with science imports
remaining lazy. Opening does not verify checksums or restore missing files.
