"""Optional readers for local fetched files; never fetch or modify cached bytes."""

from __future__ import annotations

import csv
import gzip
import io
import os
import re
from collections.abc import Mapping
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

from usdata.models import Protocol, Variable

if TYPE_CHECKING:
    from usdata._fetch import FetchedAsset
    from usdata.inspect import GribMessage

NETCDF_MEDIA_TYPES = {"application/x-netcdf", "application/netcdf", "application/x-netcdf4"}
GRIB2_MEDIA_TYPES = {
    "application/x-grib2",
    "application/grib2",
    "application/x-grib",
    "application/wmo-grib2",
}
GRIB2_SUFFIXES = (".grib2", ".grib2.gz", ".grb2", ".grb2.gz")
CSV_MEDIA_TYPES = {"text/csv", "application/csv"}
GZIP_MEDIA_TYPES = {"application/gzip", "application/x-gzip"}
OPAQUE_MEDIA_TYPES = {"", "application/octet-stream"} | GZIP_MEDIA_TYPES
PRODUCT_LEVEL = re.compile(r"^(?P<product>.+?)_\d{2}\.\d{2}$")
"""A registry variable name and the MRMS product-level suffix a decoded name drops."""

UNSET_UNITS = {"", "unknown"}
"""Unit strings that state nothing, so the registry may fill them."""

STORM_EVENTS_DATASET = "noaa:storm-events"
"""The dataset whose local timestamps the CSV reader pairs with UTC columns."""

STORM_EVENTS_UTC_COLUMNS = {"BEGIN_DATE_TIME": "BEGIN_UTC", "END_DATE_TIME": "END_UTC"}
"""Each Storm Events local timestamp column and the derived UTC column beside it."""

STORM_EVENTS_TIMEZONE_COLUMN = "CZ_TIMEZONE"
STORM_EVENTS_LOCAL_FORMAT = "%d-%b-%y %H:%M:%S"
CZ_TIMEZONE_OFFSET = re.compile(r"^[A-Za-z]+([+-]?\d{1,2})$")
"""A Storm Events timezone label, capturing the whole-hour UTC offset it ends with."""

STORM_EVENTS_RULE = (
    "local time parsed as %d-%b-%y %H:%M:%S and shifted by the whole-hour UTC "
    "offset ending CZ_TIMEZONE (CST-6 is UTC-6, GST10 is UTC+10)"
)

IBTRACS_DATASET = "noaa:ibtracs"
"""The dataset whose CSV lays a units row under the header, as ERDDAP does."""

IBTRACS_MISSING = [" ", ""]
"""What an IBTrACS CSV writes in a cell it has no value for: one space, never a word.

pandas would otherwise read the North Atlantic basin code ``NA`` as missing.
"""

IDENTIFIER_COLUMNS = {
    "station",
    "station_id",
    "site_no",
    "monitoring_location_id",
    "parameter_code",
    "statistic_id",
    "event_id",
    "episode_id",
    "state_fips",
    "cz_fips",
    "tor_other_cz_fips",
}


class MissingReaderDependency(ImportError):
    """The optional dependency required to open an asset is not installed."""


class UnsupportedFormat(ValueError):
    """No reader is implemented for this asset's format."""


class RadarDecodeError(ValueError):
    """Radar sweep metadata cannot safely pair observations with coordinates."""


class Hurdat2FormatError(ValueError):
    """A fetched file does not follow the documented HURDAT2 layout."""


def has_units_row(dataset_id: str, protocol: Protocol | None) -> bool:
    """Whether a dataset's CSV lays a units row under its header.

    ERDDAP responses do, and so does IBTrACS, which is served over plain HTTP.
    ``open`` and ``inspect`` both ask here, so they agree on which row is data.

    Args:
        dataset_id: The ``provider:name`` id the file was fetched for.
        protocol: The protocol its asset was served over, when known.

    Returns:
        True when the row under the header holds units rather than data.
    """
    return protocol is Protocol.ERDDAP or dataset_id == IBTRACS_DATASET


def _name_tables(variables: list[Variable]) -> list[tuple[bool, dict[str, Variable]]]:
    """Lookup tables from most to least specific, each flagged as case-folded or not.

    A decoded MRMS variable drops the product's level suffix, so
    ``RotationTrackML30min_00.50`` is also offered as ``RotationTrackML30min``,
    after both exact and case-insensitive matching on the full name.
    """
    named = [(variable.name, variable) for variable in variables]
    products = [
        (match["product"], variable)
        for name, variable in named
        if (match := PRODUCT_LEVEL.match(name))
    ]
    tables = []
    for fold, pairs in ((False, named), (True, named), (False, products), (True, products)):
        table: dict[str, Variable] = {}
        for name, variable in pairs:
            table.setdefault(name.casefold() if fold else name, variable)
        tables.append((fold, table))
    return tables


def _matching(tables: list[tuple[bool, dict[str, Variable]]], name: str) -> Variable | None:
    """The first registry variable a decoded name matches, or None."""
    for fold, table in tables:
        variable = table.get(name.casefold() if fold else name)
        if variable is not None:
            return variable
    return None


def _units_stated(attrs: Mapping[str, Any]) -> bool:
    """Whether the file states units, counting an empty or ``unknown`` value as silence."""
    return str(attrs.get("units", "")).strip().casefold() not in UNSET_UNITS


def fill_registry_attrs(fetched: FetchedAsset, data: Any) -> None:
    """Fill units and long names the file left unstated from the registry's variable table.

    Matches each data variable of an xarray Dataset against the entry for
    ``fetched``'s dataset by name, first exactly and then case-insensitively,
    and lists every attribute filled under ``data.attrs["usdata"]``. A value the
    file provides is never overwritten, and an asset whose dataset has no entry
    or no variables is left alone.
    """
    from usdata.registry import DatasetNotFound, default_registry

    try:
        entry = default_registry().get(fetched.asset.dataset_id)
    except DatasetNotFound:
        return
    if not entry.variables:
        return
    tables = _name_tables(entry.variables)
    filled: list[dict[str, str]] = []
    for key, array in data.data_vars.items():
        name = str(key)
        variable = _matching(tables, name)
        if variable is None:
            continue
        if variable.units and not _units_stated(array.attrs):
            array.attrs["units"] = variable.units
            filled.append({"variable": name, "attribute": "units"})
        if variable.description and "long_name" not in array.attrs:
            array.attrs["long_name"] = variable.description
            filled.append({"variable": name, "attribute": "long_name"})
    if filled:
        data.attrs["usdata"]["registry_attrs"] = filled


def _local_timestamps(pandas: Any, values: Any) -> Any:
    """Storm Events local timestamps as tz-naive datetimes, unparsable strings as NaT."""
    if pandas.api.types.is_datetime64_any_dtype(values):
        return values.dt.tz_localize(None) if values.dt.tz is not None else values
    return pandas.to_datetime(values, format=STORM_EVENTS_LOCAL_FORMAT, errors="coerce")


def derive_storm_events_utc(pandas: Any, frame: Any) -> None:
    """Add ``BEGIN_UTC`` and ``END_UTC`` to a Storm Events frame that carries the sources.

    Storm Events rows are stamped in local standard time with a ``CZ_TIMEZONE``
    label such as ``CST-6`` that no Python timezone accepts. The trailing signed
    integer is the whole-hour UTC offset, so each local timestamp is shifted by
    it and labelled UTC. Original columns are never modified, a row whose label
    or timestamp does not parse gets ``NaT``, and each derived column, its
    source, the rule, and that row count are listed under
    ``frame.attrs["usdata"]["derived"]``. A frame missing any of the three
    source columns is left alone.

    Args:
        pandas: The imported pandas module.
        frame: The DataFrame read from a Storm Events details CSV.
    """
    required = {*STORM_EVENTS_UTC_COLUMNS, STORM_EVENTS_TIMEZONE_COLUMN}
    if not required.issubset(frame.columns):
        return
    labels = frame[STORM_EVENTS_TIMEZONE_COLUMN].astype("string").str.strip()
    hours = pandas.to_numeric(labels.str.extract(CZ_TIMEZONE_OFFSET, expand=False), errors="coerce")
    offsets = pandas.to_timedelta(hours, unit="h")
    derived = []
    for source, column in STORM_EVENTS_UTC_COLUMNS.items():
        local = _local_timestamps(pandas, frame[source])
        frame[column] = (local - offsets).dt.tz_localize("UTC")
        derived.append(
            {
                "column": column,
                "source": source,
                "rule": STORM_EVENTS_RULE,
                "unparsed": int(frame[column].isna().sum()),
            }
        )
    frame.attrs["usdata"]["derived"] = derived


def inventory(path: str | os.PathLike[str]) -> list[GribMessage]:
    """List every message in a local GRIB2 file without decoding any values.

    This is the one inventory of a GRIB2 file: the reader's own "pass select"
    and "select matched no messages" errors list the same messages.

    Args:
        path: A local GRIB2 file, gzipped or not, written as a string or as any
            ``os.PathLike``. Nothing is fetched or written.

    Returns:
        One entry per message in file order, carrying the ecCodes keys that
        ``select`` matches on plus the grid shape.

    Raises:
        MissingReaderDependency: The grib extra, or the ecCodes library, is unavailable.
        ValueError: The file is not GRIB edition 2, or a message is truncated.
    """
    from usdata._grib import inventory as grib_inventory

    return grib_inventory(Path(path))


def open_asset(
    fetched: FetchedAsset,
    *,
    reader: str | None = None,
    dtype: dict[str, str] | None = None,
    parse_dates: list[str] | None = None,
    usecols: list[str] | None = None,
    nrows: int | None = None,
    sweep: int | list[int] | None = None,
    select: Mapping[str, Any] | None = None,
    strict: bool = False,
) -> Any:
    """Open local CSV, NetCDF4, GRIB2, NEXRAD, or HURDAT2 data, retaining units and provenance.

    Gzip CSVs are decompressed locally without changing cached bytes.
    Infer ``csv`` or ``erddap-csv`` from media type and protocol, or use an
    explicit reader for ambiguous metadata. An IBTrACS CSV lays a units row
    under its header as ERDDAP does, so it takes the ``erddap-csv`` reader; the
    single space it writes for a missing value is read as missing, and nothing
    else is, so the North Atlantic basin code ``NA`` stays text.
    Identifier columns default to pandas
    strings; explicit dtype entries override those defaults. Dates are not parsed
    unless named in parse_dates; use dtype to preserve numeric-looking date labels
    as strings. No checksum verification or downloading occurs.
    Radar accepts zero-based ``sweep`` indices (one integer or a non-empty list);
    the default opens the whole volume after checking sweep record alignment.
    GRIB2 accepts ``select``, a mapping of ecCodes key names to one value or a
    list of values, to choose messages from a multi-message file; a file with one
    message needs none. A select value that matches none of the selected messages
    warns, or raises ``ValueError`` when ``strict``; a select that matches nothing
    raises either way. Gzipped GRIB2 is decompressed in memory.
    HURDAT2 best-track text is recognized by dataset or filename and returns one
    row per track point; it takes no CSV options.
    A Storm Events CSV gains ``BEGIN_UTC`` and ``END_UTC`` when the frame keeps
    ``BEGIN_DATE_TIME``, ``END_DATE_TIME``, and ``CZ_TIMEZONE``: the local
    timestamp shifted by the whole-hour offset ending the timezone label, with
    unparsable rows left ``NaT`` and counted under ``attrs["usdata"]["derived"]``.
    NetCDF4 and GRIB2 results have units the file leaves missing or ``unknown``
    and missing long names filled from the registry entry's variables, listed
    under ``attrs["usdata"]["registry_attrs"]``.
    """
    if reader is None:
        media_type = (fetched.asset.media_type or "").split(";", 1)[0].strip().lower()
        name = fetched.asset.id.lower()
        gzip_csv = media_type in GZIP_MEDIA_TYPES and name.endswith(".csv.gz")
        grib2 = media_type in GRIB2_MEDIA_TYPES or (
            media_type in OPAQUE_MEDIA_TYPES and name.endswith(GRIB2_SUFFIXES)
        )
        hurdat2 = fetched.asset.dataset_id == "noaa:hurdat2" or (
            name.startswith("hurdat2-") and name.endswith(".txt")
        )
        if fetched.asset.dataset_id == "noaa:nexrad-level3":
            raise UnsupportedFormat(
                "NEXRAD Level III products have no usdata reader; open fetched.path with "
                "Py-ART (pyart.io.read_nexrad_level3) or another Level III decoder"
            )
        if fetched.asset.dataset_id == "noaa:nexrad-level2":
            reader = "nexrad-level2"
        elif hurdat2:
            reader = "hurdat2"
        elif media_type in NETCDF_MEDIA_TYPES:
            reader = "netcdf"
        elif grib2:
            reader = "grib2"
        elif media_type in CSV_MEDIA_TYPES or gzip_csv:
            units_row = has_units_row(fetched.asset.dataset_id, fetched.asset.protocol)
            reader = "erddap-csv" if units_row else "csv"
        else:
            raise UnsupportedFormat(
                f"no reader for {fetched.asset.media_type!r}; supported formats are CSV, "
                "ERDDAP CSV, NetCDF4, GRIB2, NEXRAD Level II, and HURDAT2 best tracks. "
                "For a known CSV with ambiguous metadata, "
                "pass reader='csv' "
                "or reader='erddap-csv'; otherwise use fetched.path with a format-specific reader"
            )
    if sweep is not None and reader != "nexrad-level2":
        raise ValueError("sweep applies only to the NEXRAD reader")
    if select is not None and reader != "grib2":
        raise ValueError("select applies only to the GRIB2 reader")
    if strict and reader != "grib2":
        raise ValueError("strict applies only to the GRIB2 reader")
    if reader == "grib2":
        if any(value is not None for value in (dtype, parse_dates, usecols, nrows)):
            raise ValueError(
                "CSV options dtype, parse_dates, usecols and nrows do not apply to GRIB2"
            )
        from usdata._grib import open_grib2

        return open_grib2(fetched, select=select, strict=strict)
    if reader == "netcdf":
        if any(value is not None for value in (dtype, parse_dates, usecols, nrows)):
            raise ValueError(
                "CSV options dtype, parse_dates, usecols and nrows do not apply to NetCDF"
            )
        from usdata._netcdf import open_netcdf

        return open_netcdf(fetched)
    if reader == "nexrad-level2":
        if any(value is not None for value in (dtype, parse_dates, usecols, nrows)):
            raise ValueError("dtype, parse_dates, usecols, and nrows apply only to CSV readers")
        from usdata._radar import open_nexrad

        if sweep is not None:
            values = sweep if isinstance(sweep, list) else [sweep]
            if not values or any(type(value) is not int or value < 0 for value in values):
                raise ValueError("sweep must be a nonnegative integer or non-empty list of them")
            if len(set(values)) != len(values):
                raise ValueError("sweep indices must be unique")
        return open_nexrad(fetched, sweep=sweep)
    if reader == "hurdat2":
        if any(value is not None for value in (dtype, parse_dates, usecols, nrows)):
            raise ValueError("dtype, parse_dates, usecols, and nrows apply only to CSV readers")
        from usdata._hurdat2 import open_hurdat2

        return open_hurdat2(fetched)
    if reader not in {"csv", "erddap-csv"}:
        raise UnsupportedFormat(
            f"unsupported reader {reader!r}; use 'csv', 'erddap-csv', 'netcdf', 'grib2', "
            "'nexrad-level2', or 'hurdat2'"
        )
    try:
        pandas = import_module("pandas")
    except ModuleNotFoundError as error:
        if error.name != "pandas":
            raise
        raise MissingReaderDependency(
            'CSV reading requires pandas; install it with: pip install "usdata[pandas]" '
            '(or uv add "usdata[pandas]")'
        ) from error

    # Pass a file object to pandas: reading a fetched asset is strictly local.
    with fetched.path.open("rb") as raw:
        compressed = raw.read(2) == b"\x1f\x8b"
        raw.seek(0)
        binary = gzip.GzipFile(fileobj=raw) if compressed else raw
        with io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as stream:
            records = csv.reader(stream)
            columns = next(records, [])
            if (
                not columns
                or any(not column for column in columns)
                or len(set(columns)) != len(columns)
            ):
                raise ValueError("CSV must have a non-empty header with unique column names")
            units = {}
            if reader == "erddap-csv":
                values = next(records, [])
                if len(values) != len(columns):
                    raise ValueError("ERDDAP CSV must have a units row matching the header")
                units = dict(zip(columns, (value.strip() for value in values), strict=True))
            types = {name: "string" for name in columns if name.casefold() in IDENTIFIER_COLUMNS}
            types.update(dtype or {})
            ibtracs = fetched.asset.dataset_id == IBTRACS_DATASET
            frame = pandas.read_csv(
                stream,
                header=None,
                names=columns,
                dtype=types,
                parse_dates=parse_dates,
                usecols=usecols,
                nrows=nrows,
                na_values=IBTRACS_MISSING if ibtracs else None,
                keep_default_na=not ibtracs,
                # Agency code columns are blank for most of a long file; infer them whole.
                low_memory=not ibtracs,
            )
    if units:
        frame.attrs["units"] = {name: units[name] for name in frame.columns}
    frame.attrs["usdata"] = {
        "asset_id": fetched.asset.id,
        "provenance": fetched.provenance.model_dump(mode="json"),
    }
    if fetched.asset.dataset_id == STORM_EVENTS_DATASET:
        derive_storm_events_utc(pandas, frame)
    return frame
