"""Optional readers for local fetched files; never fetch or modify cached bytes."""

from __future__ import annotations

import csv
from importlib import import_module
from typing import TYPE_CHECKING, Any

from usdata.models import Protocol

if TYPE_CHECKING:
    from usdata.fetch import FetchedAsset

CSV_MEDIA_TYPES = {"text/csv", "application/csv"}
IDENTIFIER_COLUMNS = {
    "station",
    "station_id",
    "site_no",
    "monitoring_location_id",
    "parameter_code",
    "statistic_id",
}


class MissingReaderDependency(ImportError):
    """The optional dependency required to open an asset is not installed."""


class UnsupportedFormat(ValueError):
    """No reader is implemented for this asset's format."""


def open_asset(
    fetched: FetchedAsset,
    *,
    reader: str | None = None,
    dtype: dict[str, str] | None = None,
    parse_dates: list[str] | None = None,
    usecols: list[str] | None = None,
    nrows: int | None = None,
) -> Any:
    """Read a local CSV into a pandas DataFrame, retaining units and provenance.

    Infer ``csv`` or ``erddap-csv`` from media type and protocol, or use an
    explicit reader for ambiguous metadata. Identifier columns default to pandas
    strings; explicit dtype entries override those defaults. Dates remain strings
    unless named in parse_dates. No checksum verification or downloading occurs.
    """
    if reader is None:
        media_type = (fetched.asset.media_type or "").split(";", 1)[0].strip().lower()
        if media_type not in CSV_MEDIA_TYPES:
            raise UnsupportedFormat(
                f"no reader for {fetched.asset.media_type!r}; supported formats are CSV and "
                "ERDDAP CSV. For a known CSV with ambiguous metadata, pass reader='csv' "
                "or reader='erddap-csv'; otherwise use fetched.path with a format-specific reader"
            )
        reader = "erddap-csv" if fetched.asset.protocol is Protocol.ERDDAP else "csv"
    if reader not in {"csv", "erddap-csv"}:
        raise UnsupportedFormat(f"unsupported reader {reader!r}; use 'csv' or 'erddap-csv'")
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
    with fetched.path.open(encoding="utf-8-sig", newline="") as stream:
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
            units = dict(zip(columns, values, strict=True))
        types = {name: "string" for name in columns if name.casefold() in IDENTIFIER_COLUMNS}
        types.update(dtype or {})
        frame = pandas.read_csv(
            stream,
            header=None,
            names=columns,
            dtype=types,
            parse_dates=parse_dates,
            usecols=usecols,
            nrows=nrows,
        )
    if units:
        frame.attrs["units"] = {name: units[name] for name in frame.columns}
    frame.attrs["usdata"] = {
        "asset_id": fetched.asset.id,
        "provenance": fetched.provenance.model_dump(mode="json"),
    }
    return frame
