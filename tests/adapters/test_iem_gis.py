"""IEM's zipped shapefiles: month splitting, and the canonical zip that makes fetches repeat."""

import hashlib
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from usdata.providers.noaa.iem_gis import EPOCH, canonicalize, months, write_empty_zip

SHP = b"\x00\x00\x27\x0a" + b"shape records" * 50
CSV = b"WFO,ISSUED\nOUN,202405070327\n"


def dbf(built: tuple[int, int, int]) -> bytes:
    """A DBF whose header carries the date it was built, as the service writes one."""
    return b"\x03" + bytes(built) + b"\x01\x00\x00\x00" + b"records" * 20


def service_zip(built: tuple[int, int, int, int, int, int]) -> bytes:
    """A zip as IEM sends it: deflated members stamped with the time it was built."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in (
            ("wwa.shp", SHP),
            ("wwa.dbf", dbf((built[0] - 1900, built[1], built[2]))),
            ("wwa.csv", CSV),
        ):
            archive.writestr(zipfile.ZipInfo(name, date_time=built), data)
    return buffer.getvalue()


def canonical(tmp_path: Path, data: bytes, name: str = "out.zip") -> bytes:
    source = tmp_path / f"{name}.raw"
    source.write_bytes(data)
    canonicalize(source, tmp_path / name)
    return (tmp_path / name).read_bytes()


def test_months_split_a_half_open_span_at_utc_month_boundaries() -> None:
    start = datetime(2024, 4, 30, 12, tzinfo=UTC)
    stop = datetime(2024, 6, 2, tzinfo=UTC)
    assert list(months(start, stop)) == [
        (start, datetime(2024, 5, 1, tzinfo=UTC)),
        (datetime(2024, 5, 1, tzinfo=UTC), datetime(2024, 6, 1, tzinfo=UTC)),
        (datetime(2024, 6, 1, tzinfo=UTC), stop),
    ]
    december = list(months(datetime(2024, 12, 31, tzinfo=UTC), datetime(2025, 1, 1, 1, tzinfo=UTC)))
    assert [stop for _, stop in december] == [
        datetime(2025, 1, 1, tzinfo=UTC),
        datetime(2025, 1, 1, 1, tzinfo=UTC),
    ]
    assert list(months(start, start)) == []


@pytest.mark.l2
def test_zips_built_at_different_times_canonicalize_to_the_same_bytes(tmp_path: Path) -> None:
    morning = canonical(tmp_path, service_zip((2026, 10, 8, 9, 0, 0)), "a.zip")
    next_day = canonical(tmp_path, service_zip((2026, 10, 9, 18, 35, 38)), "b.zip")
    assert morning == next_day
    # Canonicalizing is idempotent, so a canonical zip passes through unchanged.
    assert canonical(tmp_path, morning, "c.zip") == morning
    # Pinned, so a zipfile release that lays zips out differently is noticed: it would
    # change the checksum of every IEM asset already in a lockfile (ADR 0053).
    assert hashlib.sha256(morning).hexdigest() == (
        "e090645d905c65c6fe45ba4173843c31cc71e982b0037a640a8d7f3d46dff01c"
    )


@pytest.mark.l2
def test_the_canonical_zip_keeps_every_member_and_changes_only_stamps(tmp_path: Path) -> None:
    data = canonical(tmp_path, service_zip((2026, 10, 8, 18, 35, 38)))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        assert [info.filename for info in infos] == ["wwa.shp", "wwa.dbf", "wwa.csv"]
        assert {info.date_time for info in infos} == {EPOCH}
        assert {info.compress_type for info in infos} == {zipfile.ZIP_STORED}
        assert all(info.extra == b"" for info in infos)
        assert archive.read("wwa.shp") == SHP and archive.read("wwa.csv") == CSV
        # Only the DBF's last-update date changes, to 1980-01-01.
        assert archive.read("wwa.dbf") == dbf((80, 1, 1))


@pytest.mark.l2
def test_an_empty_zip_is_a_readable_zip_with_no_members(tmp_path: Path) -> None:
    write_empty_zip(tmp_path / "empty.zip")
    with zipfile.ZipFile(tmp_path / "empty.zip") as archive:
        assert archive.namelist() == []
