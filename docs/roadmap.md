# Roadmap

## Why

U.S. agencies publish scientific data through different portals, protocols, and
formats. usdata provides shared discovery, acquisition, and provenance so analyses
can declare and preserve their inputs. Scientific transformation and downstream
publishing remain the caller's responsibility.

## Now

Make the existing workflows easy to learn, reproduce, and extend. The current
architecture separates dataset adapters, transport protocols, cache/provenance,
and optional local readers. New sources should reuse those boundaries.

Use the [dataset catalog](providers/README.md) for implemented coverage,
[generated versions and targets](generated/catalog/versions.md) for registry plans,
and [changelog](../CHANGELOG.md) for completed work. Current validation results
belong in [CI](https://github.com/jakeryderv/usdata/actions/workflows/ci.yml) and
[live checks](https://github.com/jakeryderv/usdata/actions/workflows/integration.yml).

## Next candidates

These are candidates to investigate, not release commitments. Refine each into
an issue with a verified endpoint, bounded example, and acceptance criteria before
implementation. Prefer additions that exercise a useful new access pattern or
reuse an existing one:

- Further NCEI Access Data Service datasets, such as climate normals.
- Bulk directories and archives, such as HURDAT2 and IBTrACS.
- Additional GOES products/sectors, MRMS, and CO-OPS tides/currents.
- Geospatial readers when a supported dataset and representative fixtures justify them.

## Later

- [NASA access through earthaccess](https://github.com/jakeryderv/usdata/issues/9):
  establish credential ownership and authentication behavior first.
- [Remote cache backends](https://github.com/jakeryderv/usdata/issues/11):
  preserve checksum, provenance, and restoration contracts.
- [Publish the documentation at usdata.dev](https://github.com/jakeryderv/usdata/issues/56).
- GRIB2 model output with cycle/forecast-hour selection, NetCDF CDRs, and static grids.
- Further agencies, live catalog discovery, and third-party registry extensions.
- Format normalization and place-name lookup beyond states and counties.

Deferred issues have no assigned release or date. Dataset targets remain `later`
until an explicit release commitment is made.
