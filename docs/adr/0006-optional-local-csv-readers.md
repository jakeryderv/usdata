# 0006: Optional local CSV readers on fetched assets

Status: accepted. Date: 2026-09-05.

## Context

The SDK now fetches GHCN-Daily, USGS daily values, and CoastWatch SST as CSV,
but callers must account for formats and data types before analysis. In
particular, ERDDAP's second record contains units, and numeric inference can
strip leading zeros from station identifiers and observation codes.

The core must stay lightweight, raw bytes must remain reproducible, and readers
must work on locked/restored assets without consulting a mutable registry.

## Decision

Add `FetchedAsset.open()` with a lazy pandas import behind `usdata[pandas]`.
Select ordinary CSV by media type and ERDDAP CSV by media type plus protocol.
Allow explicit `csv` or `erddap-csv` selection for ambiguous metadata. This is
sufficient for current formats; defer registry reader hints and model/schema
changes until a concrete reader requires them.

Use a local file object, retain ERDDAP units in DataFrame attributes, default
known identifier/code columns to string dtype, and leave observation inference
to pandas. Expose a small set of options for dtype overrides, date parsing,
column selection, and row limits. Attach a copy of source provenance to the
in-memory result, without recording any transformation in the source sidecar.

## Consequences

Base installations and fetching do not import or install pandas. Optional
readers are tested in both dependency profiles, including isolated wheels.
The method returns a pandas DataFrame; annotations use `Any` to avoid requiring
pandas or its stubs for core consumers.

Reading does not verify integrity or perform restoration; existing `verify`
and `pull` workflows retain those responsibilities. DataFrame attributes are
convenience metadata that downstream operations or exports can discard. Saved
analyses require their own output/provenance handling. NetCDF, GRIB, radar,
and geospatial readers remain separate work with source-specific fixtures.
