"""Live check: the current Atlantic HURDAT2 file (about 7 MB of text)."""

from pathlib import Path

import pytest

from usdata import fetch
from usdata._hurdat2 import COLUMNS, parse
from usdata.cache import sha256_file
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.live

# The newest Atlantic revision, 2026-09-12, carries two upstream typos the reader
# refuses to guess at; parse the one before it until the NHC corrects the file.
READABLE = "2026-02-27"


def test_newest_atlantic_revision_resolves_and_downloads(tmp_path: Path) -> None:
    (item,) = fetch(
        default_registry().get("noaa:hurdat2"),
        build_query(basin="atlantic"),
        root=tmp_path,
    )
    assert item.asset.id.startswith("hurdat2-") and item.asset.id.endswith(".txt")
    assert item.provenance.checksum == sha256_file(item.path)
    span = item.asset.time
    assert span is not None and span.start is not None and span.end is not None
    assert span.start.year == 1851 and span.end.year >= 2025


def test_named_atlantic_revision_downloads_and_parses(tmp_path: Path) -> None:
    (item,) = fetch(
        default_registry().get("noaa:hurdat2"),
        build_query(basin="atlantic", revision=READABLE),
        root=tmp_path,
    )
    assert item.asset.id == "hurdat2-1851-2025-02272026.txt"
    span = item.asset.time
    assert span is not None and span.end is not None

    columns = parse(item.path.read_text(encoding="utf-8"))
    assert set(columns) == set(COLUMNS)
    storms = set(columns["storm_id"])
    assert len(columns["time"]) > 50_000 and len(storms) > 1_800
    assert {"AL011851", "AL092021"} <= storms
    assert min(columns["time"]).year == 1851
    assert max(columns["time"]).year >= span.end.year


@pytest.mark.live
def test_reader_infers_hurdat2_and_signs_coordinates(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    (item,) = fetch(
        default_registry().get("noaa:hurdat2"),
        build_query(basin="atlantic", revision=READABLE),
        root=tmp_path,
    )
    frame = item.open()
    assert list(frame.columns) == COLUMNS
    ida = frame[frame.storm_id == "AL092021"]
    assert (ida["name"] == "IDA").all() and (ida.longitude < 0).all()
    assert ida.max_wind_kt.max() == 130.0
    assert frame.attrs["usdata"]["provenance"]["checksum"] == item.provenance.checksum
