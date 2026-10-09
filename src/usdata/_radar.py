"""Local NEXRAD Level II decoding behind the radar extra."""

from __future__ import annotations

import bz2
import gzip
import struct
from datetime import UTC, datetime, timedelta
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

from usdata.readers import MissingReaderDependency, RadarDecodeError, source_attrs

# NOAA RDA/RPG ICD 2620002Y, Table XVII-I notes 21 and 30.
MOMENT_FLAG_COUNTS = {
    "DBZH": 2,
    "VRADH": 2,
    "WRADH": 2,
    "ZDR": 2,
    "PHIDP": 2,
    "RHOHV": 2,
    "CCORH": 8,
}

MOMENT_NAMES = {
    "REF": "DBZH",
    "VEL": "VRADH",
    "SW": "WRADH",
    "ZDR": "ZDR",
    "PHI": "PHIDP",
    "RHO": "RHOHV",
    "CFP": "CCORH",
}
"""Each NEXRAD data block and the name xradar, and so ``open_nexrad``, gives its moment."""

LEGACY_UNDECODED = {"SW"}
"""Legacy message-1 blocks xradar 0.12 reads but does not return.

It labels message-1 spectrum width ``SW`` while its name table holds only the
message-31 spelling ``SW `` (with a trailing space), so a legacy volume opens
without ``WRADH``. A listing says what ``open_nexrad`` returns, so it leaves the
block out too.
"""

LEGACY_ANGLE_SCALE = 180 / (4096 * 8)
"""Degrees per unit of a legacy message-1 angle; message 31 states degrees."""

PIP_HINT = (
    'NEXRAD reading requires xradar; install it with: pip install "usdata[radar]" '
    '(or uv add "usdata[radar]")'
)

if TYPE_CHECKING:
    from usdata._fetch import FetchedAsset
    from usdata.inspect import NexradSummary


def _import(name: str) -> Any:
    """An xradar module, or ``MissingReaderDependency`` naming the extra."""
    try:
        return import_module(name)
    except ModuleNotFoundError as error:
        if error.name != "xradar":
            raise
        raise MissingReaderDependency(PIP_HINT) from error


def _content(path: Path) -> bytes:
    """A volume's bytes, with any whole-file gzip or bzip2 wrapper removed."""
    content = path.read_bytes()
    if content.startswith(b"\x1f\x8b"):
        return gzip.decompress(content)
    if content.startswith(b"BZh"):
        return bz2.decompress(content)
    return content


def _collected(ray: dict[str, Any]) -> datetime:
    """When a radial was collected: NEXRAD counts days from 1 January 1970 as day 1."""
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
        days=ray["collect_date"] - 1, milliseconds=ray["collect_ms"]
    )


def summary(path: Path) -> NexradSummary:
    """Every sweep of a local volume, read from its metadata without decoding any moment.

    Raises:
        MissingReaderDependency: The radar extra is not installed.
        ValueError: The bytes are not a readable NEXRAD Level II volume.
    """
    from usdata.inspect import NexradSummary, NexradSweep

    backend = _import("xradar.io.backends.nexrad_level2")
    try:
        with backend.NEXRADLevel2File(_content(path), loaddata=False) as volume:
            incomplete = volume.incomplete_sweeps
            vcp = volume.msg_5 or {}
            cuts = vcp.get("elevation_data") or []
            sweeps = []
            for index, (data, rays) in enumerate(
                zip(volume.msg_31_data_header, volume.msg_31_header, strict=False)
            ):
                first = rays[0]
                number = first["elevation_number"]
                legacy = data["msg_type"] == 1
                cut = cuts[number - 1] if 0 < number <= len(cuts) else None
                angle = cut["elevation_angle"] if cut else first["elevation_angle"]
                flags = (cut or {}).get("supplemental_data_decoded", {})
                blocks = [
                    block.strip()
                    for block in data["msg_31_data_header"]
                    if not (legacy and block.strip() in LEGACY_UNDECODED)
                ]
                sweeps.append(
                    NexradSweep(
                        index=index,
                        elevation_number=number,
                        fixed_angle=angle * LEGACY_ANGLE_SCALE if legacy else angle,
                        moments=[MOMENT_NAMES[b] for b in blocks if b in MOMENT_NAMES],
                        start=_collected(first),
                        end=_collected(rays[-1]),
                        rays=len(rays),
                        complete=index not in incomplete,
                        sails=bool(flags.get("sails_cut")) if cut else None,
                        mrle=bool(flags.get("mrle_cut")) if cut else None,
                    )
                )
    except (struct.error, EOFError, KeyError, IndexError, TypeError) as error:
        raise ValueError(f"not a readable NEXRAD Level II volume: {error}") from error
    return NexradSummary(vcp=vcp.get("pattern_number"), sweeps=sweeps)


def _check_sweeps(content: bytes, sweep: int | list[int] | None) -> None:
    """Reject decoder tables that pair a sweep with another sweep's coordinates.

    xradar 0.12 can omit an interior sweep without an end marker from its data
    table while keeping its moment metadata. The coordinate list then shifts.
    Compare record identities, not just ray counts: equal-length sweeps can
    otherwise silently acquire another sweep's coordinates and timestamps.
    """
    backend = import_module("xradar.io.backends.nexrad_level2")
    with backend.NEXRADLevel2File(content, loaddata=False) as volume:
        # Parsing completeness also populates the per-sweep data tables.
        _ = volume.incomplete_sweeps
        moments = volume.msg_31_data_header
        coordinates = volume.msg_31_header
        requested = (
            list(range(len(moments)))
            if sweep is None
            else (sweep if isinstance(sweep, list) else [sweep])
        )
        for index in requested:
            if index >= len(moments):
                raise ValueError(f"sweep {index} is outside this volume's {len(moments)} sweeps")
            data = volume.data.get(index)
            rays = coordinates[index] if index < len(coordinates) else []
            # Non-radial messages may occur within a sweep or after its last
            # received ray. Follow the decoder's traversal, excluding those
            # records, instead of requiring record_end to be a radial message.
            expected_records = []
            if data is not None:
                intermediate = {record["record_number"] for record in data["intermediate_records"]}
                expected_records = [
                    record
                    for record in range(data["record_number"], data["record_end"] + 1)
                    if record not in intermediate
                ]
            if (
                data is None
                or not rays
                or moments[index]["record_number"] != data["record_number"]
                or [ray["record_number"] for ray in rays] != expected_records
            ):
                raise RadarDecodeError(
                    f"cannot safely decode sweep {index}: NEXRAD moment and coordinate records "
                    "do not agree; select an unaffected sweep explicitly with "
                    "open_nexrad(sweep=...) or use another decoder. "
                    "No sweeps were silently dropped."
                )


def open_nexrad(fetched: FetchedAsset, *, sweep: int | list[int] | None = None) -> Any:
    """Decode a local volume into a fully loaded xarray DataTree."""
    xradar = _import("xradar")
    # Bytes prevent remote URL interpretation and work across the backend's
    # repeated sweep reads. Compressed source files stay unchanged in the cache.
    content = _content(fetched.path)
    _check_sweeps(content, sweep)
    radar = xradar.io.open_nexradlevel2_datatree(content, sweep=sweep, incomplete_sweep="pad")
    try:
        radar.load()
    finally:
        radar.close()
    for node in radar.subtree:
        for name, variable in node.ds.variables.items():
            # The backend records the entire input byte string as `source`.
            # Provenance below is the durable reference, not that decoder buffer.
            variable.encoding.pop("source", None)
            if name in MOMENT_FLAG_COUNTS and "range" in variable.dims:
                scale = variable.encoding.get("scale_factor")
                offset = variable.encoding.get("add_offset")
                if scale is not None and offset is not None:
                    # xradar 0.12 does not supply _FillValue for NEXRAD flags.
                    # Compare using each moment's native scale, not fixed units.
                    data = node[name]
                    valid = data.notnull()
                    for code in range(MOMENT_FLAG_COUNTS[name]):
                        valid = valid & (data != offset + code * scale)
                    masked = data.where(valid)
                    masked.encoding = data.encoding.copy()
                    node[name] = masked
    radar.attrs["usdata"] = {
        **source_attrs(fetched),
        "sweeps": [name.lstrip("/") for name in radar.groups if name.startswith("/sweep_")],
    }
    return radar
