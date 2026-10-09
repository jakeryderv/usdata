"""What IEM's GIS download services share: monthly requests and a canonical zip.

The Iowa Environmental Mesonet serves the NWS watch, warning, and advisory
archive and the SPC outlook archive as zipped shapefiles, built on request for a
UTC window. Two things about those answers shape both adapters (ADR 0053):

- A request is capped: one year of warnings when nothing else narrows it, ten
  outlook years. Every window is therefore split at UTC month boundaries, one
  request each, so no request comes near either cap and a long window becomes
  assets of a size one fetch can hold.
- The answer differs between identical requests. Each zip member is stamped
  with the time the zip was built, and the DBF header with the date, while the
  members' contents are otherwise the same byte for byte. ``fetch`` therefore
  writes a canonical zip: the same members in the same order, each stored
  uncompressed and stamped 1980-01-01 00:00, with no extra fields, and the
  DBF's last-update date set to 1980-01-01. Storing rather than deflating keeps
  the bytes independent of the zlib a machine has. ``transformations`` says so
  in every provenance sidecar.
"""

from __future__ import annotations

import shutil
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from usdata._files import TEMP_SUFFIX
from usdata.models import Asset
from usdata.protocols import http
from usdata.providers.http import HttpProvider

EPOCH = (1980, 1, 1, 0, 0, 0)
"""The timestamp every member of a canonical zip carries, the earliest a zip can hold."""

DBF_DATE = bytes([80, 1, 1])
"""The DBF last-update date written in place of the build date: 1980-01-01, as years since 1900."""

CANONICAL_ZIP = (
    "iem canonical zip: members kept in order, stored uncompressed with timestamps fixed "
    "at 1980-01-01 00:00 and no extra fields; the DBF header's last-update date set to "
    "1980-01-01"
)
"""The ``transformations`` entry every fetch from these services records."""

_CHUNK = 1 << 20


def months(start: datetime, stop: datetime) -> Iterator[tuple[datetime, datetime]]:
    """Split the half-open UTC span ``[start, stop)`` at month boundaries, in order."""
    cursor = start
    while cursor < stop:
        if cursor.month == 12:
            boundary = datetime(cursor.year + 1, 1, 1, tzinfo=UTC)
        else:
            boundary = datetime(cursor.year, cursor.month + 1, 1, tzinfo=UTC)
        end = min(boundary, stop)
        yield cursor, end
        cursor = end


def stamp(value: datetime) -> str:
    """A UTC instant as the services read it, to the second."""
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def last_second(stop: datetime) -> datetime:
    """The inclusive end of a half-open span that stops at ``stop``, to the second."""
    return stop - timedelta(seconds=1)


def canonicalize(source: Path, dest: Path) -> None:
    """Write the canonical form of the zip at ``source`` to ``dest``.

    Raises:
        zipfile.BadZipFile: ``source`` is not a zip.
    """
    with (
        zipfile.ZipFile(source) as archive,
        zipfile.ZipFile(dest, "w", zipfile.ZIP_STORED) as out,
    ):
        for info in archive.infolist():
            member = zipfile.ZipInfo(info.filename, date_time=EPOCH)
            member.compress_type = zipfile.ZIP_STORED
            # ZipInfo defaults both from the running platform; fix them so every machine agrees.
            member.create_system = 3
            member.external_attr = 0o644 << 16
            with archive.open(info) as reader, out.open(member, "w") as writer:
                if info.filename.lower().endswith(".dbf"):
                    head = reader.read(4)
                    writer.write(head[:1] + DBF_DATE if len(head) == 4 else head)
                shutil.copyfileobj(reader, writer, _CHUNK)


def write_empty_zip(dest: Path) -> None:
    """Write a zip with no members, the canonical form of an answer that holds nothing."""
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_STORED):
        pass


class IemShapefiles(HttpProvider):
    """An IEM GIS service read one zipped shapefile per request, written canonically."""

    transformations = (CANONICAL_ZIP,)

    no_results: bytes | None = None
    """The plain-text body the service sends in place of a zip that would hold nothing.

    ``None`` for a service that answers an empty window with an empty shapefile.
    """

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download the zip and write its canonical form, or an empty zip for no results."""
        # A hidden sibling ending in the temporary suffix, so an abandoned one is recognised.
        raw = dest.with_name(f".{dest.name.lstrip('.').removesuffix(TEMP_SUFFIX)}.raw{TEMP_SUFFIX}")
        try:
            http.download(asset.href, raw, self._http())
            if zipfile.is_zipfile(raw):
                canonicalize(raw, dest)
                return dest
            with raw.open("rb") as f:
                body = f.read(512)
        finally:
            raw.unlink(missing_ok=True)
        if self.no_results is not None and body.strip().startswith(self.no_results):
            write_empty_zip(dest)
            return dest
        raise httpx.DecodingError(
            "IEM answered with something other than a zip: "
            + body.decode("utf-8", "replace").strip()[:300]
        )
