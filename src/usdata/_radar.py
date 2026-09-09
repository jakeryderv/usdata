"""Local NEXRAD Level II decoding behind the radar extra."""

from __future__ import annotations

import bz2
import gzip
from importlib import import_module
from typing import TYPE_CHECKING, Any

from usdata.readers import MissingReaderDependency

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


def open_nexrad(fetched: FetchedAsset) -> Any:
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
    radar = xradar.io.open_nexradlevel2_datatree(content, incomplete_sweep="pad")
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
    }
    return radar
