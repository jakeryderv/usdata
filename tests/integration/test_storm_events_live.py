"""Bounded live check: NCEI's small 1950 details archive (about 11 KB)."""

import csv
import gzip
from pathlib import Path

import pytest

from usdata.cache import sha256_file
from usdata.fetch import fetch
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.integration


def test_annual_details_download_retains_gzip_and_original_schema(tmp_path: Path) -> None:
    (item,) = fetch(
        default_registry().get("noaa:storm-events"),
        build_query(start="1950-01-01", end="1950-12-31"),
        root=tmp_path,
    )
    assert item.path.read_bytes().startswith(b"\x1f\x8b")
    assert item.provenance.checksum == sha256_file(item.path)
    assert item.asset.size == item.provenance.size
    with gzip.open(item.path, "rt", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows and all(row["YEAR"] == "1950" for row in rows)
    assert {"EVENT_ID", "EVENT_TYPE", "STATE", "TOR_F_SCALE"} <= rows[0].keys()
