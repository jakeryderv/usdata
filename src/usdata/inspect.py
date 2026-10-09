"""Format-aware summaries of one fetched file: what it is and what it holds.

An inspection is local and read-only. It reads the file and the provenance
beside it, never fetches, verifies, or writes anything, and never changes cached
bytes. CSV is summarized with the standard library, so no extra is needed;
NetCDF4, GRIB2, and NEXRAD Level II use the same extras ``open`` does, and a
missing one yields a summary whose detail is ``None`` and whose ``note`` names
the extra to install.
"""

from __future__ import annotations

import csv
import gzip
import io
import os
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from usdata import provenance, readers
from usdata.models import AwareUTC, Protocol, Provenance

if TYPE_CHECKING:
    from usdata._fetch import FetchedAsset

ROW_LIMIT = 100_000
"""Data rows a CSV scan reads before it stops and reports the count as a lower bound."""

CSV_SUFFIXES = (".csv", ".csv.gz")
NETCDF_SUFFIXES = (".nc", ".nc4", ".cdf", ".netcdf")
"""Names that identify a format when no media type does, as for a cached file."""


class AssetFormat(StrEnum):
    """The format an inspection recognized; ``bytes`` when none of the others applies."""

    CSV = "csv"
    NETCDF = "netcdf"
    GRIB2 = "grib2"
    NEXRAD = "nexrad"
    BYTES = "bytes"


class CsvSummary(BaseModel):
    """A delimited text file's header and how many data rows the scan counted."""

    columns: list[str] = Field(description="Header fields, in file order")
    units: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Units per column, from the units row an ERDDAP or IBTrACS CSV lays under its "
            "header; empty for a CSV with no such row"
        ),
    )
    row_count: int = Field(
        ge=0, description="Data rows counted, excluding the header and any units row"
    )
    row_limit: int = Field(gt=0, description="Rows the scan reads before it stops")
    truncated: bool = Field(description="The scan stopped early, so row_count is a lower bound")


class NetcdfVariable(BaseModel):
    """One NetCDF4 data variable's shape and the metadata the file states for it."""

    name: str
    dims: list[str] = Field(description="Dimension names, in array order")
    shape: list[int] = Field(description="Length of each dimension, in array order")
    units: str | None = None
    long_name: str | None = None


class NetcdfSummary(BaseModel):
    """The data variables of a NetCDF4 file's root group."""

    variables: list[NetcdfVariable]


class GribMessage(BaseModel):
    """One GRIB2 message as ecCodes reports it: the keys ``select`` matches on, plus the grid.

    Two numberings name the same message. ``file_index`` counts messages in the
    local file from zero; ``object_index`` is the number the source object's
    index sidecar gave it, one-based, and is set only for a partial fetch, as is
    ``selector``, the index selector the message was fetched for.
    """

    file_index: int = Field(
        ge=0,
        description="Zero-based message position in the local file; fields of one message share it",
    )
    object_index: int | None = Field(
        default=None,
        ge=1,
        description="One-based message number in the source object, for a partial fetch",
    )
    selector: str | None = Field(
        default=None, description="Index selector this message was fetched for, for a partial fetch"
    )
    short_name: str | None = Field(default=None, description="ecCodes shortName")
    base_name: str | None = Field(
        default=None,
        description=(
            "Name the reader starts this message's variable from: shortName, or where "
            "ecCodes has none, the MRMS product or parameter_<discipline>_<category>_<number>"
        ),
    )
    name: str | None = Field(default=None, description="ecCodes name")
    type_of_level: str | None = Field(default=None, description="ecCodes typeOfLevel")
    level: str | None = Field(default=None, description="ecCodes level")
    step: str | None = Field(default=None, description="ecCodes step")
    units: str | None = Field(default=None, description="ecCodes units")
    shape: tuple[int, int] | None = Field(default=None, description="Grid rows and columns")


class Grib2Summary(BaseModel):
    """Every message a GRIB2 file holds, in file order."""

    messages: list[GribMessage]

    def variable_for(self, selector: str) -> str:
        """The variable name ``open()`` will give the message one index selector fetched.

        This closes the loop a partial fetch opens: ``messages="CAPE:surface"``
        asks in the index sidecar's vocabulary, and the reader answers in
        ecCodes', so this says which name that selector produces given every
        message this file holds. Only a partial fetch records selectors.

        Args:
            selector: A selector exactly as the provenance recorded it, such as
                ``CAPE:surface``.

        Returns:
            The variable name the GRIB2 naming rule gives that message.

        Raises:
            KeyError: No message here was fetched for that selector; the message
                lists the selectors that were.
            ValueError: That selector fetched a message holding several fields,
                as RAP publishes wind components, and the record was written
                before each field's selector was recorded, so it cannot say
                which field it named; the message lists their variables.
        """
        from usdata._grib import variable_names

        names = variable_names(
            [
                (
                    message.base_name or message.short_name or "",
                    message.type_of_level,
                    message.level,
                )
                for message in self.messages
            ]
        )
        matched = [
            name
            for message, name in zip(self.messages, names, strict=True)
            if message.selector == selector
        ]
        if len(matched) > 1:
            # An older record keeps one selector per range, and one range can hold several fields.
            raise ValueError(
                f"selector {selector!r} fetched one message holding {len(matched)} fields "
                f"({', '.join(matched)}); pick the variable by name"
            )
        if matched:
            return matched[0]
        recorded = ", ".join(
            repr(message.selector) for message in self.messages if message.selector is not None
        )
        raise KeyError(
            f"no message in this file was fetched for selector {selector!r}; "
            f"selectors recorded here: {recorded or 'none'}"
        )


class NexradSweep(BaseModel):
    """One sweep of a NEXRAD Level II volume, read from its metadata without decoding moments.

    ``index`` is what ``open_nexrad(sweep=...)`` takes. It is not an elevation:
    a split cut scans one angle twice, once for reflectivity and dual-pol
    moments and once for velocity, and SAILS or MRLE rescan the lowest angle
    several times a volume, so one angle can hold many indices. Choose sweeps
    here by ``fixed_angle``, ``moments``, and ``start``, then open them by index.
    """

    index: int = Field(
        ge=0, description="Zero-based position in the volume; what open_nexrad(sweep=...) takes"
    )
    elevation_number: int = Field(ge=1, description="The one-based VCP cut the sweep scans")
    fixed_angle: float = Field(
        description=(
            "Elevation in degrees: the VCP table's angle for the cut, or the first ray's "
            "where the volume carries no VCP table"
        )
    )
    moments: list[str] = Field(
        description=(
            "Moments open_nexrad returns for the sweep, by its names; a legacy volume's "
            "spectrum width is in the file but not decoded"
        )
    )
    start: AwareUTC = Field(description="When the sweep's first ray was collected")
    end: AwareUTC = Field(description="When its last ray was collected")
    rays: int = Field(ge=0, description="Rays received")
    complete: bool = Field(
        description="The sweep reached its end; open_nexrad pads one that did not"
    )
    sails: bool | None = Field(
        default=None, description="A SAILS low-level rescan; None where there is no VCP table"
    )
    mrle: bool | None = Field(
        default=None, description="An MRLE mid-volume rescan; None where there is no VCP table"
    )


class NexradSummary(BaseModel):
    """The volume coverage pattern and every sweep of a NEXRAD Level II volume, in scan order."""

    vcp: int | None = Field(description="Volume coverage pattern number; None for a legacy volume")
    sweeps: list[NexradSweep]


class Summary(BaseModel):
    """What one fetched file is, where it came from, and what its format holds.

    Exactly one of ``csv``, ``netcdf``, ``grib2``, and ``nexrad`` is set, or none of them
    when the format is bytes-only, its reader is unavailable, or the bytes no
    longer decode; ``note`` then says why. ``detail`` returns whichever is set.
    """

    dataset_id: str
    asset_id: str
    path: Path
    size: int = Field(ge=0, description="Bytes on disk now, not the size provenance recorded")
    format: AssetFormat
    retrieved_at: AwareUTC
    checksum: str
    source_url: str
    csv: CsvSummary | None = None
    netcdf: NetcdfSummary | None = None
    grib2: Grib2Summary | None = None
    nexrad: NexradSummary | None = None
    note: str | None = Field(
        default=None, description="Why a recognized format yielded no detail, when it did not"
    )

    @property
    def detail(self) -> CsvSummary | NetcdfSummary | Grib2Summary | NexradSummary | None:
        """The per-format detail, or None for a bytes-only file or an unavailable reader."""
        return self.csv or self.netcdf or self.grib2 or self.nexrad


def inspect_asset(fetched: FetchedAsset) -> Summary:
    """Summarize a fetched asset: its provenance and, for its format, what is inside.

    The format comes from the asset's media type, falling back to its id, so a
    restored asset summarizes the same way a freshly fetched one does.

    Args:
        fetched: The asset to inspect, as ``fetch`` returned it.

    Returns:
        A summary carrying the detail for the asset's format, or no detail and a
        note naming the extra when that format's reader is not installed.
    """
    return _summarize(
        fetched.path,
        fetched.asset.id,
        fetched.provenance,
        _detect(fetched.asset.id, fetched.asset.media_type, fetched.asset.dataset_id),
        fetched.asset.protocol,
    )


def inspect_path(path: str | os.PathLike[str]) -> Summary:
    """Summarize a cached file, reading the provenance sidecar written beside it.

    Args:
        path: A cached file whose ``<name>.provenance.json`` sidecar exists,
            written as a string or as any ``os.PathLike``.

    Returns:
        The summary ``inspect_asset`` builds, with the format taken from the file
        name because a sidecar records no media type, and the protocol from the
        registry entry of the dataset the sidecar names, for the same reason.

    Raises:
        OSError: The file or its provenance sidecar is missing or unreadable.
        ValueError: The sidecar is not a provenance record.
    """
    local = Path(path)
    record = provenance.read(local)
    return _summarize(
        local,
        local.name,
        record,
        _detect(local.name, None, record.dataset_id),
        _registered_protocol(record),
    )


def _registered_protocol(record: Provenance) -> Protocol | None:
    """The protocol the registry gives the dataset a sidecar names, or None when it has none."""
    from usdata.registry import DatasetNotFound, default_registry

    try:
        return default_registry().get(record.dataset_id).protocol
    except DatasetNotFound:
        return None


def _summarize(
    path: Path, asset_id: str, record: Provenance, fmt: AssetFormat, protocol: Protocol | None
) -> Summary:
    """One summary, with the detail its format allows and a note where it allows none."""
    detail: CsvSummary | NetcdfSummary | Grib2Summary | NexradSummary | None = None
    note: str | None = None
    if fmt is not AssetFormat.BYTES:
        try:
            detail = _detail(path, asset_id, fmt, record, protocol)
        except readers.MissingReaderDependency as error:
            note = str(error)
        # A cached file that no longer decodes is reported, not raised: a summary
        # of where the bytes came from is still worth having.
        except (csv.Error, EOFError, OSError, ValueError) as error:
            note = f"not readable as {fmt.value}: {type(error).__name__}: {error}"
    return Summary(
        dataset_id=record.dataset_id,
        asset_id=asset_id,
        path=path,
        size=path.stat().st_size,
        format=fmt,
        retrieved_at=record.retrieved_at,
        checksum=record.checksum,
        source_url=record.source_url,
        csv=detail if isinstance(detail, CsvSummary) else None,
        netcdf=detail if isinstance(detail, NetcdfSummary) else None,
        grib2=detail if isinstance(detail, Grib2Summary) else None,
        nexrad=detail if isinstance(detail, NexradSummary) else None,
        note=note,
    )


def _detect(name: str, media_type: str | None, dataset_id: str) -> AssetFormat:
    """The format to summarize: the dataset's where it has one, then the media type, then the name.

    NEXRAD Level II volumes are served as opaque bytes under names that state no
    format, so they are known by their dataset, as ``open`` knows them.
    """
    if dataset_id == readers.NEXRAD_LEVEL2:
        return AssetFormat.NEXRAD
    kind = (media_type or "").split(";", 1)[0].strip().lower()
    if kind in readers.GRIB2_MEDIA_TYPES:
        return AssetFormat.GRIB2
    if kind in readers.NETCDF_MEDIA_TYPES:
        return AssetFormat.NETCDF
    if kind in readers.CSV_MEDIA_TYPES:
        return AssetFormat.CSV
    if kind not in readers.OPAQUE_MEDIA_TYPES:
        return AssetFormat.BYTES
    lowered = name.lower()
    if lowered.endswith(readers.GRIB2_SUFFIXES):
        return AssetFormat.GRIB2
    if lowered.endswith(NETCDF_SUFFIXES):
        return AssetFormat.NETCDF
    if lowered.endswith(CSV_SUFFIXES):
        return AssetFormat.CSV
    return AssetFormat.BYTES


def _detail(
    path: Path, asset_id: str, fmt: AssetFormat, record: Provenance, protocol: Protocol | None
) -> CsvSummary | NetcdfSummary | Grib2Summary | NexradSummary:
    """The detail for one recognized format, reading only what that format needs.

    A GRIB2 inventory is given the asset id, which names a message ecCodes
    cannot, as the reader names it.
    """
    if fmt is AssetFormat.CSV:
        return _csv_summary(path, units_row=readers.has_units_row(record.dataset_id, protocol))
    if fmt is AssetFormat.NETCDF:
        from usdata._netcdf import variables

        return NetcdfSummary(variables=variables(path))
    if fmt is AssetFormat.NEXRAD:
        from usdata._radar import summary

        return summary(path)
    from usdata._grib import inventory

    return Grib2Summary(messages=_paired(inventory(path, asset_id), record))


def _paired(messages: list[GribMessage], record: Provenance) -> list[GribMessage]:
    """Each message as the fetch that took it described it, where provenance says.

    The file itself carries neither number nor selector: a partial fetch recorded
    one message number per range and one selector per field, and ``file_index``
    counts the file's messages the same way, so the fields of a message that
    holds several all pair with its number and each with its own selector. A
    whole file, or a record that does not pair, leaves both unset.
    """
    numbers = record.object_messages
    if not numbers or any(message.file_index >= len(numbers) for message in messages):
        return messages
    paired = len(record.selectors) == len(numbers)
    fields_seen: dict[int, int] = {}
    result = []
    for message in messages:
        field = fields_seen[message.file_index] = fields_seen.get(message.file_index, -1) + 1
        selector = record.field_selector(message.file_index, field) if paired else None
        result.append(
            message.model_copy(
                update={"object_index": numbers[message.file_index], "selector": selector}
            )
        )
    return result


def _csv_summary(path: Path, *, units_row: bool = False) -> CsvSummary:
    """Header and data-row count through the standard library, stopping at ``ROW_LIMIT`` rows.

    With ``units_row`` the row under the header is read as units, as ``open``
    reads it, rather than counted as data.

    Raises:
        ValueError: A units row was expected and does not match the header.
    """
    with path.open("rb") as raw:
        compressed = raw.read(2) == b"\x1f\x8b"
        raw.seek(0)
        binary = gzip.GzipFile(fileobj=raw) if compressed else raw
        with io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as stream:
            records = csv.reader(stream)
            columns = next(records, [])
            units: dict[str, str] = {}
            if units_row and columns:
                values = next(records, [])
                if len(values) != len(columns):
                    raise ValueError("CSV must have a units row matching the header")
                units = dict(zip(columns, (value.strip() for value in values), strict=True))
            rows = 0
            for _ in records:
                rows += 1
                if rows == ROW_LIMIT:
                    break
            truncated = next(records, None) is not None
    return CsvSummary(
        columns=columns, units=units, row_count=rows, row_limit=ROW_LIMIT, truncated=truncated
    )


__all__ = [
    "ROW_LIMIT",
    "AssetFormat",
    "CsvSummary",
    "Grib2Summary",
    "GribMessage",
    "NetcdfSummary",
    "NetcdfVariable",
    "NexradSummary",
    "NexradSweep",
    "Summary",
    "inspect_asset",
    "inspect_path",
]
