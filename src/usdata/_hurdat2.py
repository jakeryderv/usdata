"""Local HURDAT2 best-track parsing into a tidy track-point table, behind pandas.

The source format is a sequence of storm headers, each followed by the exact
number of track-point lines it declares. Nothing about that structure is
queryable upstream, so the value of the dataset is in this reader: it returns one
row per track point with UTC timestamps, signed coordinates, and documented
missing-value sentinels converted to NaN.
"""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from importlib import import_module
from typing import TYPE_CHECKING, Any

from usdata.readers import MissingReaderDependency

if TYPE_CHECKING:
    from usdata.fetch import FetchedAsset

STORM_ID = re.compile(r"[A-Z]{2}\d{6}")
TEXT_COLUMNS = ["storm_id", "name", "record_identifier", "status"]
RADII_COLUMNS = [
    f"r{threshold}_{quadrant}_nm"
    for threshold in (34, 50, 64)
    for quadrant in ("ne", "se", "sw", "nw")
]
NUMERIC_COLUMNS = [
    "latitude",
    "longitude",
    "max_wind_kt",
    "min_pressure_mb",
    *RADII_COLUMNS,
    "max_wind_radius_nm",
]
COLUMNS = ["storm_id", "name", "time", "record_identifier", "status", *NUMERIC_COLUMNS]
# Date, time, record identifier, and status precede the measurements. Radius of
# maximum wind was appended for the 2021 season; older revisions stop one short.
TRACK_FIELDS = len(NUMERIC_COLUMNS) + 4
# Documented missing-data sentinels: -999 for pressure, wind radii, and RMW; -99
# for the unassigned intensities of the 1967 non-developing depressions.
MISSING = {-999, -99}


class Hurdat2FormatError(ValueError):
    """A fetched file does not follow the documented HURDAT2 layout."""


def _measurement(text: str, line: int) -> float:
    """One integer measurement, with documented missing sentinels as NaN."""
    digits = text[1:] if text.startswith("-") else text
    if not (digits.isascii() and digits.isdigit()):
        raise Hurdat2FormatError(f"line {line}: expected an integer measurement, got {text!r}")
    value = int(text)
    return math.nan if value in MISSING else float(value)


def _coordinate(text: str, axis: str, positive: str, negative: str, line: int) -> float:
    """A hemisphere-suffixed coordinate as signed decimal degrees."""
    hemisphere, magnitude = text[-1:].upper(), text[:-1]
    limit = 90.0 if axis == "latitude" else 180.0
    try:
        degrees = float(magnitude)
    except ValueError:
        degrees = math.nan
    if hemisphere not in (positive, negative) or not 0.0 <= degrees <= limit:
        raise Hurdat2FormatError(
            f"line {line}: expected a {axis} like '28.0{positive}', got {text!r}"
        )
    return -degrees if hemisphere == negative else degrees


def _track_point(fields: list[str], line: int) -> tuple[Any, ...]:
    """One data line as its timestamp, record codes, and numeric measurements."""
    if fields and not fields[-1]:
        fields = fields[:-1]  # Some revisions terminate data lines with a comma.
    if len(fields) not in (TRACK_FIELDS - 1, TRACK_FIELDS):
        raise Hurdat2FormatError(
            f"line {line}: expected {TRACK_FIELDS - 1} or {TRACK_FIELDS} comma-separated "
            f"track fields, got {len(fields)}"
        )
    try:
        when = datetime.strptime(f"{fields[0]}{fields[1]}", "%Y%m%d%H%M").replace(tzinfo=UTC)
    except ValueError as error:
        raise Hurdat2FormatError(
            f"line {line}: expected a UTC date and time like '20210829, 1655', "
            f"got {fields[0]!r}, {fields[1]!r}"
        ) from error
    values = [
        _coordinate(fields[4], "latitude", "N", "S", line),
        _coordinate(fields[5], "longitude", "E", "W", line),
        *(_measurement(text, line) for text in fields[6:]),
    ]
    if len(values) < len(NUMERIC_COLUMNS):
        values.append(math.nan)  # Radius of maximum wind predates the 2021 format.
    return when, fields[2] or None, fields[3] or None, values


def parse(text: str) -> dict[str, list[Any]]:
    """Read whole-file HURDAT2 text into per-column lists, one entry per track point."""
    columns: dict[str, list[Any]] = {name: [] for name in COLUMNS}
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        header = [field.strip() for field in lines[index].split(",")]
        line = index + 1
        index += 1
        if header == [""]:
            continue
        if len(header) < 3 or not STORM_ID.fullmatch(header[0]) or any(header[3:]):
            raise Hurdat2FormatError(
                f"line {line}: expected a storm header like 'AL011851, UNNAMED, 14,'"
            )
        if not (header[2].isascii() and header[2].isdigit()):
            raise Hurdat2FormatError(
                f"line {line}: track-point count {header[2]!r} is not a nonnegative integer"
            )
        count = int(header[2])
        if index + count > len(lines):
            raise Hurdat2FormatError(
                f"line {line}: storm {header[0]} declares {count} track points "
                f"but only {len(lines) - index} lines follow"
            )
        for offset in range(count):
            body = [field.strip() for field in lines[index + offset].split(",")]
            when, identifier, status, values = _track_point(body, index + offset + 1)
            columns["storm_id"].append(header[0])
            columns["name"].append(header[1])
            columns["time"].append(when)
            columns["record_identifier"].append(identifier)
            columns["status"].append(status)
            for name, value in zip(NUMERIC_COLUMNS, values, strict=True):
                columns[name].append(value)
        index += count
    return columns


def open_hurdat2(fetched: FetchedAsset) -> Any:
    """Parse a fetched HURDAT2 file into a pandas DataFrame of track points."""
    try:
        pandas = import_module("pandas")
    except ModuleNotFoundError as error:
        if error.name != "pandas":
            raise
        raise MissingReaderDependency(
            'HURDAT2 reading requires pandas; install it with: pip install "usdata[pandas]" '
            '(or uv add "usdata[pandas]")'
        ) from error
    # Reading a fetched asset is strictly local; the source file is never rewritten.
    columns = parse(fetched.path.read_text(encoding="utf-8"))
    data: dict[str, Any] = {
        name: pandas.array(columns[name], dtype="string") for name in TEXT_COLUMNS
    }
    data["time"] = pandas.to_datetime(columns["time"], utc=True)
    data.update({name: pandas.array(columns[name], dtype="float64") for name in NUMERIC_COLUMNS})
    frame = pandas.DataFrame(data, columns=COLUMNS)
    frame.attrs["usdata"] = {
        "asset_id": fetched.asset.id,
        "provenance": fetched.provenance.model_dump(mode="json"),
    }
    return frame
