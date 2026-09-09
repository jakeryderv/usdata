"""Local NEXRAD Level II decoding behind the radar extra."""

from __future__ import annotations

import bz2
import gzip
from importlib import import_module
from typing import TYPE_CHECKING, Any

from usdata.readers import MissingReaderDependency, RadarDecodeError

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

if TYPE_CHECKING:
    from usdata.fetch import FetchedAsset


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
            if (
                data is None
                or not rays
                or moments[index]["record_number"] != data["record_number"]
                or rays[0]["record_number"] != data["record_number"]
                or rays[-1]["record_number"] != data["record_end"]
            ):
                raise RadarDecodeError(
                    f"cannot safely decode sweep {index}: NEXRAD moment and coordinate records "
                    "do not agree; select an unaffected sweep explicitly with open(sweep=...) "
                    "or use another decoder. No sweeps were silently dropped."
                )


def open_nexrad(fetched: FetchedAsset, *, sweep: int | list[int] | None = None) -> Any:
    """Decode a local volume into a fully loaded xarray DataTree."""
    try:
        xradar = import_module("xradar")
    except ModuleNotFoundError as error:
        if error.name != "xradar":
            raise
        raise MissingReaderDependency(
            'NEXRAD reading requires xradar; install it with: pip install "usdata[radar]" '
            '(or uv add "usdata[radar]")'
        ) from error

    # Bytes prevent remote URL interpretation and work across the backend's
    # repeated sweep reads. Compressed source files stay unchanged in the cache.
    content = fetched.path.read_bytes()
    if content.startswith(b"\x1f\x8b"):
        content = gzip.decompress(content)
    elif content.startswith(b"BZh"):
        content = bz2.decompress(content)
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
        "asset_id": fetched.asset.id,
        "provenance": fetched.provenance.model_dump(mode="json"),
        "sweeps": [name.lstrip("/") for name in radar.groups if name.startswith("/sweep_")],
    }
    return radar
