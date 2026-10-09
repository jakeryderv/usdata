"""Small live IEM warning archive queries: every product in a window, pinned and restored."""

import csv
import io
import zipfile
from pathlib import Path

import pytest

from usdata.pull import pull, verify

pytestmark = pytest.mark.live


def rows(path: Path) -> list[dict[str, str]]:
    """The attribute rows of a fetched zip, read from the CSV IEM puts beside the shapefile."""
    with zipfile.ZipFile(path) as archive:
        (name,) = [name for name in archive.namelist() if name.endswith(".csv")]
        return list(csv.DictReader(io.StringIO(archive.read(name).decode())))


def test_the_may_2024_outbreak_pinned_and_restored_byte_for_byte(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: outbreak-warnings
sources:
  - name: oklahoma
    dataset: noaa:nws-warnings
    location: Oklahoma
    start: 2024-05-06T18:00Z
    end: 2024-05-07T12:00Z
    params: {events: "TO.W,TO.A"}
  - name: everything
    dataset: noaa:nws-warnings
    start: 2024-05-07T03:00Z
    end: 2024-05-07T03:27Z
""")
    result = pull(manifest, root=tmp_path / "cache")
    oklahoma = rows(result.one("oklahoma").path)
    assert {(row["PHENOM"], row["SIG"]) for row in oklahoma} == {("TO", "W"), ("TO", "A")}
    assert {row["GTYPE"] for row in oklahoma} == {"P", "C"}
    # Osage County's tornado watch, issued at 19:05 UTC, is one of the watch's county rows.
    watch = [row for row in oklahoma if row["NWS_UGC"] == "OKC113" and row["PHENOM"] == "TO"]
    assert ("2024-05-06 19:05", "A") in {(row["ISSUED"], row["SIG"]) for row in watch}
    # Every product, issued from 03:00 through the minute 03:27 inclusive.
    everything = rows(result.one("everything").path)
    assert len(everything) == 136
    assert max(row["ISSUED"] for row in everything) == "2024-05-07 03:27"
    assert {row["PHENOM"] + "." + row["SIG"] for row in everything} >= {"TO.A", "SV.W", "FA.Y"}
    with zipfile.ZipFile(result.one("everything").path) as archive:
        assert {info.date_time for info in archive.infolist()} == {(1980, 1, 1, 0, 0, 0)}
    # IEM builds a new zip on every request; the canonical form restores to the pinned bytes.
    for name in ("oklahoma", "everything"):
        result.one(name).path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and not restored.one("everything").from_cache
    assert verify(manifest, root=tmp_path / "cache") == []
