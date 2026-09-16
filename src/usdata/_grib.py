"""Local, eagerly loaded GRIB2 reading through ecCodes behind the grib extra.

Messages are decoded one at a time with the ecCodes Python bindings, never
cfgrib. The reader builds the xarray Dataset itself: one data variable per
selected message on one shared grid, coordinates computed from the grid
definition, and provenance under ``attrs["usdata"]``. Variable names follow
from the set of selected messages alone, never from which short names happen to
repeat, so the same select always yields the same names. Values arrive from
ecCodes as float64, are masked to NaN where the message's bitmap marks them
missing, and are stored as float32; the float64 array is released before the
Dataset is returned. Rows are ordered north to south and columns west to east
regardless of the message's scanning mode. See ADR 0022.
"""

from __future__ import annotations

import gzip
import re
import warnings
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib import import_module
from inspect import currentframe
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

from usdata.inspect import GribMessage
from usdata.readers import MissingReaderDependency, fill_registry_attrs

if TYPE_CHECKING:
    from usdata._fetch import FetchedAsset

PIP_HINT = 'GRIB2 reading requires eccodes and xarray; install: pip install "usdata[grib]"'
LIBRARY_HINT = (
    "the eccodes Python package is installed but the ecCodes library could not be loaded; "
    "on macOS and on Windows with Python 3.14 install it separately, for example "
    "`conda install -c conda-forge eccodes` or `brew install eccodes`"
)
MRMS_NAME = re.compile(r"^MRMS_(?P<product>.+?)_\d{2}\.\d{2}_\d{8}-\d{6}\.grib2(?:\.gz)?$")
INVENTORY_KEYS = ("shortName", "name", "typeOfLevel", "level", "step", "units")
VARIABLE_KEYS = (
    "name",
    "units",
    "typeOfLevel",
    "level",
    "discipline",
    "parameterCategory",
    "parameterNumber",
    "packingType",
    "dataDate",
    "dataTime",
    "validityDate",
    "validityTime",
    "step",
    "stepType",
    "gridType",
)
PROJECTION_KEYS = (
    "LaDInDegrees",
    "LoVInDegrees",
    "Latin1InDegrees",
    "Latin2InDegrees",
    "latitudeOfFirstGridPointInDegrees",
    "longitudeOfFirstGridPointInDegrees",
    "DxInMetres",
    "DyInMetres",
    "shapeOfTheEarth",
)


def _modules() -> tuple[Any, Any, Any]:
    try:
        eccodes = import_module("eccodes")
        xarray = import_module("xarray")
        numpy = import_module("numpy")
    except ModuleNotFoundError as error:
        if error.name not in {"eccodes", "gribapi", "xarray", "numpy"}:
            raise
        raise MissingReaderDependency(PIP_HINT) from error
    except (RuntimeError, OSError) as error:
        # eccodes imports, then findlibs fails to locate the shared library.
        raise MissingReaderDependency(f"{LIBRARY_HINT} ({error})") from error
    return eccodes, xarray, numpy


@contextmanager
def _handle(eccodes: Any, handle: int) -> Iterator[int]:
    try:
        yield handle
    finally:
        eccodes.codes_release(handle)


def _messages_from_bytes(eccodes: Any, data: bytes) -> Iterator[int]:
    """Handles for each message in an in-memory GRIB byte string, using section 0 lengths."""
    offset = 0
    while offset < len(data):
        if data[offset : offset + 4] != b"GRIB":
            raise ValueError(f"not a GRIB message at byte {offset}")
        if data[offset + 7] != 2:
            raise ValueError("only GRIB edition 2 is supported")
        length = int.from_bytes(data[offset + 8 : offset + 16], "big")
        if length < 16 or offset + length > len(data):
            raise ValueError(f"truncated GRIB message at byte {offset}")
        with _handle(eccodes, eccodes.codes_new_from_message(data[offset : offset + length])) as h:
            yield h
        offset += length


def _messages(eccodes: Any, path: Path) -> Iterator[int]:
    """Handles for each message, decompressing gzip in memory without changing cached bytes."""
    with path.open("rb") as probe:
        compressed = probe.read(2) == b"\x1f\x8b"
    if compressed:
        data = gzip.decompress(path.read_bytes())
        yield from _messages_from_bytes(eccodes, data)
        return
    # ecCodes reads through the descriptor, so it gets a file object it alone positions.
    with path.open("rb") as raw:
        while (handle := eccodes.codes_grib_new_from_file(raw)) is not None:
            with _handle(eccodes, handle) as h:
                if eccodes.codes_get(h, "edition") != 2:
                    raise ValueError("only GRIB edition 2 is supported")
                yield h


def _get(eccodes: Any, h: int, key: str, ktype: type | None = None) -> Any:
    if not eccodes.codes_is_defined(h, key):
        return None
    try:
        return eccodes.codes_get(h, key, ktype) if ktype else eccodes.codes_get(h, key)
    except Exception:
        return None


def _options(key: str, wanted: Any) -> list[Any]:
    """One key's wanted values as a validated list, whether one value or several were given."""
    options = list(wanted) if isinstance(wanted, list | tuple | set) else [wanted]
    if not options:
        raise ValueError(f"select[{key!r}] must not be empty")
    for option in options:
        if isinstance(option, bool) or not isinstance(option, int | float | str):
            raise ValueError(f"select[{key!r}] values must be strings or numbers")
    return options


def _matched(eccodes: Any, h: int, key: str, options: list[Any]) -> set[int]:
    """Positions in ``options`` that this message's value for ``key`` matches."""
    text = _get(eccodes, h, key, str)
    number = _get(eccodes, h, key, float) if text is not None else None
    hits = set()
    for index, option in enumerate(options):
        if isinstance(option, str):
            if text == option:
                hits.add(index)
        elif number is not None and number == option:
            hits.add(index)
    return hits


def _unmatched_report(
    options: Mapping[str, list[Any]],
    matched: Mapping[str, set[int]],
    present: Mapping[str, list[str]],
) -> str:
    """Text naming every select value that matched no message, with what was there instead."""
    parts = []
    for key, wanted in options.items():
        missing = [option for index, option in enumerate(wanted) if index not in matched[key]]
        if not missing:
            continue
        available = ", ".join(repr(value) for value in present[key]) or "none"
        parts.append(
            f"select[{key!r}] matched no message for "
            f"{', '.join(repr(option) for option in missing)}; "
            f"{key} values available with the other select keys: {available}."
        )
    return " ".join(parts)


def _caller_stacklevel() -> int:
    """Stack level of the first frame outside usdata, so a warning points at the caller."""
    package = Path(__file__).resolve().parent
    frame = currentframe()
    frame = frame.f_back if frame is not None else None
    level = 1
    while frame is not None and Path(frame.f_code.co_filename).resolve().is_relative_to(package):
        level += 1
        frame = frame.f_back
    return level


def _shape(eccodes: Any, h: int) -> tuple[int, int] | None:
    """A message's grid rows and columns under either key pair, or None when neither is set."""
    rows, cols = _get(eccodes, h, "Nj", int), _get(eccodes, h, "Ni", int)
    if rows is None or cols is None:
        rows, cols = _get(eccodes, h, "Ny", int), _get(eccodes, h, "Nx", int)
    return None if rows is None or cols is None else (rows, cols)


def inventory(path: Path) -> list[GribMessage]:
    """Every message in a local GRIB2 file, in file order, without decoding its values."""
    eccodes = _modules()[0]
    messages = []
    for index, h in enumerate(_messages(eccodes, path)):
        keys = {key: _get(eccodes, h, key, str) for key in INVENTORY_KEYS}
        messages.append(
            GribMessage(
                file_index=index,
                short_name=keys["shortName"],
                name=keys["name"],
                type_of_level=keys["typeOfLevel"],
                level=keys["level"],
                step=keys["step"],
                units=keys["units"],
                shape=_shape(eccodes, h),
            )
        )
    return messages


def _available(path: Path) -> str:
    """Every message as a (shortName, typeOfLevel, level) triple, for a reader error to list."""
    return ", ".join(
        f"({message.short_name!r}, {message.type_of_level!r}, {message.level!r})"
        for message in inventory(path)
    )


def _product_name(asset_id: str) -> str | None:
    match = MRMS_NAME.match(asset_id)
    return match["product"] if match else None


def _time(date: Any, time: Any) -> str | None:
    if date is None or time is None:
        return None
    try:
        return (
            datetime.strptime(f"{int(date):08d}{int(time):04d}", "%Y%m%d%H%M")
            .replace(tzinfo=UTC)
            .isoformat()
        )
    except ValueError:
        return None


class _Grid:
    """One message's grid: shape, row/column flips, dimension names, and coordinates."""

    def __init__(self, eccodes: Any, numpy: Any, h: int) -> None:
        self.grid_type = _get(eccodes, h, "gridType", str) or "unknown"
        shape = _shape(eccodes, h)
        if shape is None:
            raise ValueError(f"cannot determine the grid shape of a {self.grid_type} message")
        self.shape = shape
        rows, cols = shape
        self.flip_rows = bool(_get(eccodes, h, "jScansPositively", int))
        self.flip_cols = bool(_get(eccodes, h, "iScansNegatively", int))
        if _get(eccodes, h, "jPointsAreConsecutive", int):
            raise ValueError("grids with consecutive j points are not supported")
        self.regular = self.grid_type == "regular_ll"
        self.dims = ("latitude", "longitude") if self.regular else ("y", "x")
        self.attrs: dict[str, Any] = {"gridType": self.grid_type}
        if self.regular:
            first_lat = _get(eccodes, h, "latitudeOfFirstGridPointInDegrees", float)
            first_lon = _get(eccodes, h, "longitudeOfFirstGridPointInDegrees", float)
            dlat = _get(eccodes, h, "jDirectionIncrementInDegrees", float)
            dlon = _get(eccodes, h, "iDirectionIncrementInDegrees", float)
            if None in (first_lat, first_lon, dlat, dlon):
                raise ValueError("regular grid without first point and increments")
            lat = first_lat + (1 if self.flip_rows else -1) * dlat * numpy.arange(rows)
            lon = first_lon + (-1 if self.flip_cols else 1) * dlon * numpy.arange(cols)
            self.coords = {
                "latitude": self._orient(numpy, lat, rows=True),
                "longitude": self._orient(numpy, lon, rows=False),
            }
        else:
            lat = self.reshape(numpy, eccodes.codes_get_double_array(h, "latitudes"))
            lon = self.reshape(numpy, eccodes.codes_get_double_array(h, "longitudes"))
            self.coords = {"latitude": (self.dims, lat), "longitude": (self.dims, lon)}
            for key in PROJECTION_KEYS:
                value = _get(eccodes, h, key)
                if value is not None:
                    self.attrs[key] = value
        self.key = (self.grid_type, self.shape, self.flip_rows, self.flip_cols)

    def _orient(self, numpy: Any, axis: Any, *, rows: bool) -> Any:
        return axis[::-1].copy() if (self.flip_rows if rows else self.flip_cols) else axis

    def reshape(self, numpy: Any, flat: Any) -> Any:
        if flat.size != self.shape[0] * self.shape[1]:
            raise ValueError(f"message has {flat.size} values for a {self.shape} grid")
        grid = flat.reshape(self.shape)
        if self.flip_rows:
            grid = grid[::-1, :]
        if self.flip_cols:
            grid = grid[:, ::-1]
        return numpy.ascontiguousarray(grid)


class _Field(NamedTuple):
    """One decoded message: its short name, values, variable attributes, and identity."""

    short: str
    data: Any
    attrs: dict[str, Any]
    message: dict[str, Any]


def variable_names(fields: Sequence[tuple[str, Any, Any]]) -> list[str]:
    """The names one set of selected messages takes, under the one GRIB2 naming rule.

    Every name is the bare short name while the messages share one type of level
    and level, and every name is ``short_typeOfLevel_level`` as soon as they span
    more than one, so the names follow from the selection rather than from which
    short names happened to repeat. A name that would still repeat gains its
    position.

    Args:
        fields: One ``(short name, type of level, level)`` triple per message, in
            the order the messages appear.

    Returns:
        One variable name per field, in the same order.
    """
    spans = len({(level_type, level) for _, level_type, level in fields}) > 1
    names: list[str] = []
    for short, level_type, level in fields:
        label = short
        if spans:
            kind = "level" if level_type is None else level_type
            label = f"{short}_{kind}_{'' if level is None else level}"
        if label in names:
            label = f"{label}_{len(names)}"
        names.append(label)
    return names


def open_grib2(
    fetched: FetchedAsset, select: Mapping[str, Any] | None = None, *, strict: bool = False
) -> Any:
    """Decode selected GRIB2 messages into one loaded xarray Dataset.

    A file of several messages needs ``select``, unless its provenance says the
    fetch already selected them: a partial fetch concatenated the messages that
    were asked for, so all of them are wanted and ``select`` stays optional.

    Variables take their ``shortName`` when every selected message shares one
    type of level and level, and ``shortName_typeOfLevel_level`` for all of
    them as soon as the selection spans more than one, so the names follow from
    the select rather than from which short names happened to repeat.
    ``attrs["usdata"]["messages"]`` maps each variable name to the message it
    came from: ``file_index`` numbers it in this file from zero, and
    ``object_index`` numbers it in the source object as that object's index
    sidecar does, one-based, for a partial fetch and ``None`` for a whole file.
    A partial fetch's entries also carry ``selector``, the index selector the
    message was fetched for.

    A select value that matches none of the selected messages warns, or raises
    ``ValueError`` when ``strict``; a select that matches nothing always raises.
    """
    eccodes, xarray, numpy = _modules()
    if select is not None and not isinstance(select, Mapping):
        raise ValueError("select must be a mapping of ecCodes key names to values")
    options = {key: _options(key, wanted) for key, wanted in (select or {}).items()}
    matched: dict[str, set[int]] = {key: set() for key in options}
    present: dict[str, list[str]] = {key: [] for key in options}
    selected: list[_Field] = []
    grid: _Grid | None = None
    count = 0
    needs_select = select is None and not fetched.provenance.is_partial
    object_messages = fetched.provenance.object_messages
    selectors = fetched.provenance.selectors if object_messages else []
    for h in _messages(eccodes, fetched.path):
        count += 1
        if count > 1 and needs_select:
            continue
        hits = {key: _matched(eccodes, h, key, wanted) for key, wanted in options.items()}
        missed = [key for key, indexes in hits.items() if not indexes]
        for key in options:
            # What this key could have been with the rest of the select held fixed.
            if missed not in ([], [key]):
                continue
            value = _get(eccodes, h, key, str)
            if value is not None and value not in present[key]:
                present[key].append(value)
        if missed:
            continue
        for key, indexes in hits.items():
            matched[key] |= indexes
        message_grid = _Grid(eccodes, numpy, h)
        if grid is None:
            grid = message_grid
        elif message_grid.key != grid.key:
            raise ValueError("selected messages lie on different grids; narrow select to one grid")
        values = eccodes.codes_get_double_array(h, "values")
        if _get(eccodes, h, "bitmapPresent", int) or (
            _get(eccodes, h, "numberOfMissing", int) or 0
        ):
            missing = _get(eccodes, h, "missingValue", float)
            if missing is not None:
                values[values == missing] = numpy.nan
        data = grid.reshape(numpy, values).astype(numpy.float32)
        del values
        attrs = {
            key: value for key in VARIABLE_KEYS if (value := _get(eccodes, h, key)) is not None
        }
        for label, date_key, time_key in (
            ("reference_time", "dataDate", "dataTime"),
            ("valid_time", "validityDate", "validityTime"),
        ):
            stamp = _time(attrs.get(date_key), attrs.get(time_key))
            if stamp:
                attrs[label] = stamp
        message: dict[str, Any] = {
            "file_index": count - 1,
            "object_index": object_messages[count - 1] if object_messages else None,
            "shortName": _get(eccodes, h, "shortName", str),
            "typeOfLevel": attrs.get("typeOfLevel"),
            "level": attrs.get("level"),
            "step": attrs.get("step"),
        }
        if selectors:
            message["selector"] = selectors[count - 1]
        short = message["shortName"]
        if short in (None, "", "unknown", "~"):
            short = _product_name(fetched.asset.id) or (
                f"parameter_{attrs.get('discipline')}_{attrs.get('parameterCategory')}"
                f"_{attrs.get('parameterNumber')}"
            )
        selected.append(_Field(short=short, data=data, attrs=attrs, message=message))
    if count > 1 and needs_select:
        raise ValueError(
            f"{count} messages; pass select={{...}} with ecCodes keys to choose, "
            f"for example select={{'shortName': ..., 'typeOfLevel': ...}}. "
            f"Available (shortName, typeOfLevel, level): {_available(fetched.path)}"
        )
    if grid is None or not selected:
        if not count:
            raise ValueError("no GRIB2 messages found")
        raise ValueError(
            "select matched no messages. Available (shortName, typeOfLevel, level): "
            f"{_available(fetched.path)}"
        )
    if report := _unmatched_report(options, matched, present):
        if strict:
            raise ValueError(report)
        warnings.warn(report, UserWarning, stacklevel=_caller_stacklevel())
    variables: dict[str, Any] = {}
    messages: dict[str, dict[str, Any]] = {}
    names = variable_names(
        [
            (field.short, field.attrs.get("typeOfLevel"), field.attrs.get("level"))
            for field in selected
        ]
    )
    for label, field in zip(names, selected, strict=True):
        variables[label] = (grid.dims, field.data, field.attrs)
        messages[label] = field.message
    dataset = xarray.Dataset(variables, coords=grid.coords)
    dataset.latitude.attrs["units"] = "degrees_north"
    dataset.longitude.attrs["units"] = "degrees_east"
    dataset.attrs.update(grid.attrs)
    dataset.attrs["usdata"] = {
        "asset_id": fetched.asset.id,
        "provenance": fetched.provenance.model_dump(mode="json"),
        "messages": messages,
    }
    fill_registry_attrs(fetched, dataset)
    return dataset
