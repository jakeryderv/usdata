# 0042: One open method per format, and a bare `open()` that infers

Status: accepted. Date: 2026-09-24. Updates
[ADR 0006](0006-optional-local-csv-readers.md), and moves the options of
[ADR 0011](0011-radar-sweep-alignment.md) and
[ADR 0022](0022-grib2-reader-backend.md) onto their own methods.

## Context

`FetchedAsset.open()` took the options of every reader: `dtype`,
`parse_dates`, `usecols`, and `nrows` for CSV, `sweep` for NEXRAD Level II,
`select` and `strict` for GRIB2, and `reader` to override inference. Each reader
that gained an option widened the one signature, and most combinations were
meaningless, so `open_asset` held five blocks of runtime checks such as "sweep
applies only to the NEXRAD reader" to reject them. A new reader with options
would have added a sixth.

The result was typed `Any`, because `open()` returns a pandas DataFrame, an
xarray Dataset, or an xarray DataTree depending on the file. ADR 0006 chose
`Any` so that core consumers need neither pandas nor its stubs. It also meant
an editor knew nothing about any result, including in the walkthroughs, where
the format is always known.

The walkthroughs show how the options are used: `parse_dates` nine times,
`dtype` eight, `sweep` five, `usecols` four, and `select` once, with every call
on a file whose format the notebook already names. `reader` was used only by
tests. Every caller is in this repository, and before 1.0 a minor release may
break the API if the changelog says so ([versioning](../versioning.md)).

## Decision

`open()` takes no options. It infers the reader as before and runs it with its
defaults.

Each format with options gets its own method on `FetchedAsset`, taking only
that format's options and declaring what it returns:

| Method | Returns | Options |
|---|---|---|
| `open_csv` | `pandas.DataFrame` | `dtype`, `parse_dates`, `usecols`, `nrows`, `units_row` |
| `open_nexrad` | `xarray.DataTree` | `sweep` |
| `open_grib2` | `xarray.Dataset` | `select`, `strict` |
| `open_netcdf` | `xarray.Dataset` | none |

`usdata.readers` has a function of the same name for each, taking the fetched
asset first, and `open_asset` keeps inference only. A method opens the file as
its format whatever the asset's metadata says, which replaces `reader` as the
way to open a file whose metadata is ambiguous. For CSV the one remaining choice
`reader` made, between `csv` and `erddap-csv`, becomes `units_row`: `None` infers
it as `open()` does, and `True` or `False` says whether a units row follows the
header. HURDAT2 and AQS daily JSON take no options and get no method, since
`open()` already opens them and a method would only restate the inference.

The return types are imported under `TYPE_CHECKING`, with the missing-import
diagnostic suppressed where the extra is absent. Nothing is imported at run
time, so ADR 0006's constraint holds: a core install needs neither pandas nor
stubs. A type checker that can see pandas or xarray types the result; one that
cannot sees an unknown type, which is what `Any` gave before.

The old keyword arguments are removed rather than deprecated. There is no
deprecation window before 1.0, every caller was in this repository and has
moved, and a type checker now reports a stale call as an unknown parameter.

## Consequences

A call names its format, so a notebook reads as what it opens:
`item.open_nexrad(sweep=0)` rather than `item.open(sweep=0)`. The five
cross-option checks are gone, because an option can no longer reach a reader it
does not belong to. The price is that the caller has to know the format, and
that a method called on the wrong file fails in its decoder rather than with a
message about options. Where the format is unknown, `open()` still infers it.

`FetchedAsset` has five open methods instead of one. A new reader with options
adds a method rather than widening a shared signature. A new reader without
options adds only a branch to inference.

`open()` stays typed `Any`, since its result depends on the file. A caller who
wants a typed result names the format.

A strict-mode type checker without pandas installed reports an unknown type
where it previously saw `Any`. Calling `open_csv` without pandas raises
`MissingReaderDependency` anyway, so this only affects code that type-checks a
call it cannot run.
