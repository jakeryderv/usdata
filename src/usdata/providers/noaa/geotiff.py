"""The georeferencing a GeoTIFF states in its first image, read with byte-range requests.

Only what places the image is read: its size, ``ModelPixelScale``,
``ModelTiepoint``, and the model and raster types from the GeoKey directory.
Classic TIFF and BigTIFF are both read, in either byte order. Nothing is
decoded; the pixels are never requested. Used by the emergency response imagery
adapter, which reads one tile per collection to learn how large its tiles are.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from usdata.protocols import http

HEAD_BYTES = 65536
"""How much the first request reads: a cloud-optimized GeoTIFF keeps its headers there."""

WIDTH, HEIGHT = 256, 257
PIXEL_SCALE, TIEPOINT, GEOKEYS = 33550, 33922, 34735
MODEL_TYPE_KEY, RASTER_TYPE_KEY, PROJECTED_CRS_KEY = 1024, 1025, 3072
MODEL_PROJECTED, MODEL_GEOGRAPHIC = 1, 2
RASTER_PIXEL_IS_POINT = 2
MAX_ENTRIES = 4096
MAX_VALUE_BYTES = 1 << 20
"""Bounds on what a directory may claim, so a corrupt one cannot ask for gigabytes."""
# TIFF field types: struct code and size.
TYPES = {3: ("H", 2), 4: ("I", 4), 12: ("d", 8), 16: ("Q", 8)}


class GeoTiffError(ValueError):
    """The bytes are not a GeoTIFF this module can place."""


@dataclass(frozen=True)
class Georeference:
    """Where the first image of a GeoTIFF lies, in its model's units (degrees or metres)."""

    width: int
    height: int
    west: float
    north: float
    pixel_width: float
    pixel_height: float
    model_type: int | None
    """1 for a projected model, 2 for a geographic one, None when the file states no GeoKeys."""
    projected_crs: int | None = None
    """The EPSG code of a projected model's coordinate system, such as 3857, when stated."""

    @property
    def span(self) -> tuple[float, float]:
        """Width and height of the image's area, in model units."""
        return self.width * self.pixel_width, self.height * self.pixel_height

    @property
    def extent(self) -> tuple[float, float, float, float]:
        """West, south, east, and north edges of the image's area, in model units."""
        span_x, span_y = self.span
        return self.west, self.north - span_y, self.west + span_x, self.north


Read = Callable[[int, int], bytes]
"""Return ``length`` bytes from ``offset``; fewer only at the end of the file."""


def parse(head: bytes, read: Read) -> Georeference:
    """The georeference stated by a GeoTIFF whose first bytes are ``head``.

    ``read`` supplies any byte range beyond ``head`` that the image file
    directory points at.

    Raises:
        GeoTiffError: The bytes are not a TIFF, or its first image is not georeferenced
            by a pixel scale and a tiepoint.
    """

    def take(offset: int, length: int) -> bytes:
        data = (
            head[offset : offset + length] if offset + length <= len(head) else read(offset, length)
        )
        if len(data) != length:
            raise GeoTiffError(f"TIFF ends before byte {offset + length}")
        return data

    order = {b"II": "<", b"MM": ">"}.get(head[:2])
    if order is None or len(head) < 16:
        raise GeoTiffError("not a TIFF file")
    magic = struct.unpack(order + "H", head[2:4])[0]
    if magic == 42:
        big, first = False, struct.unpack(order + "I", head[4:8])[0]
    elif magic == 43 and struct.unpack(order + "HH", head[4:8]) == (8, 0):
        big, first = True, struct.unpack(order + "Q", head[8:16])[0]
    else:
        raise GeoTiffError("not a TIFF file")
    if first < 8:
        raise GeoTiffError("the TIFF names no image file directory")
    count_format, entry_size, inline = ("Q", 20, 8) if big else ("H", 12, 4)
    count_size = struct.calcsize(count_format)
    (count,) = struct.unpack(order + count_format, take(first, count_size))
    if count > MAX_ENTRIES:
        raise GeoTiffError(f"the first image file directory claims {count} entries")
    entries = take(first + count_size, count * entry_size)
    tags: dict[int, tuple[float | int, ...]] = {}
    for index in range(count):
        entry = entries[index * entry_size : (index + 1) * entry_size]
        tag, kind = struct.unpack(order + "HH", entry[:4])
        if tag not in (WIDTH, HEIGHT, PIXEL_SCALE, TIEPOINT, GEOKEYS) or kind not in TYPES:
            continue
        code, size = TYPES[kind]
        if big:
            (number,) = struct.unpack(order + "Q", entry[4:12])
            field = entry[12:20]
        else:
            (number,) = struct.unpack(order + "I", entry[4:8])
            field = entry[8:12]
        length = number * size
        if length > MAX_VALUE_BYTES:
            raise GeoTiffError(f"tag {tag} claims {length} bytes")
        if length <= inline:
            data = field[:length]
        else:
            (offset,) = struct.unpack(order + ("Q" if big else "I"), field)
            data = take(offset, length)
        tags[tag] = struct.unpack(order + code * number, data)
    return _georeference(tags)


def _georeference(tags: dict[int, tuple[float | int, ...]]) -> Georeference:
    missing = [
        name
        for tag, name in (
            (PIXEL_SCALE, "ModelPixelScale"),
            (TIEPOINT, "ModelTiepoint"),
            (WIDTH, "ImageWidth"),
            (HEIGHT, "ImageLength"),
        )
        if tag not in tags
    ]
    if missing:
        raise GeoTiffError(f"the first image states no {' or '.join(missing)}")
    scale, tie = tags[PIXEL_SCALE], tags[TIEPOINT]
    if len(scale) < 2 or len(tie) < 6 or scale[0] <= 0 or scale[1] <= 0:
        raise GeoTiffError("the first image's pixel scale or tiepoint is malformed")
    keys = _geokeys(tags.get(GEOKEYS, ()))
    pixel_width, pixel_height = float(scale[0]), float(scale[1])
    # The tiepoint ties raster (i, j) to model (x, y); a point-registered raster
    # ties pixel centres, so its area begins half a pixel earlier.
    shift = 0.5 if keys.get(RASTER_TYPE_KEY) == RASTER_PIXEL_IS_POINT else 0.0
    column, row, x, y = float(tie[0]), float(tie[1]), float(tie[3]), float(tie[4])
    return Georeference(
        width=int(tags[WIDTH][0]),
        height=int(tags[HEIGHT][0]),
        west=x - (column + shift) * pixel_width,
        north=y + (row + shift) * pixel_height,
        pixel_width=pixel_width,
        pixel_height=pixel_height,
        model_type=keys.get(MODEL_TYPE_KEY),
        projected_crs=keys.get(PROJECTED_CRS_KEY),
    )


def _geokeys(directory: tuple[float | int, ...]) -> dict[int, int]:
    """The GeoKeys whose value is stored inline in the directory, by key id."""
    values = [int(value) for value in directory]
    if len(values) < 4:
        return {}
    keys: dict[int, int] = {}
    for start in range(4, 4 + 4 * values[3], 4):
        key, location, _count, value = values[start : start + 4]
        if location == 0:
            keys[key] = value
    return keys


def read_georeference(url: str, client: httpx.Client) -> Georeference:
    """The georeference of the GeoTIFF at ``url``, read in one or a few byte ranges.

    Raises:
        GeoTiffError: The object is not a GeoTIFF this module can place.
        httpx.HTTPError: A request failed.
    """

    def read(offset: int, length: int) -> bytes:
        headers = {"Range": f"bytes={offset}-{offset + length - 1}"}
        return http.get(url, client, headers=headers).content[:length]

    return parse(read(0, HEAD_BYTES), read)
