"""Bounded live checks: NCEI's small 1950 details archive and one year of the sibling tables."""

import csv
import gzip
from pathlib import Path

import pytest

from usdata import fetch
from usdata.cache import sha256_file
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.live


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


def test_the_sibling_tables_join_to_details_on_event_id(tmp_path: Path) -> None:
    dataset = default_registry().get("noaa:storm-events")
    rows = {}
    for table in ("fatalities", "locations"):
        (item,) = fetch(
            dataset, build_query(start="1996-01-01", end="1996-12-31", table=table), root=tmp_path
        )
        assert f"StormEvents_{table}-ftp_v1.0_d1996_c" in item.asset.id
        with gzip.open(item.path, "rt", encoding="utf-8", newline="") as stream:
            rows[table] = list(csv.DictReader(stream))
    assert rows["fatalities"] and {"FATALITY_ID", "EVENT_ID", "FATALITY_LOCATION"} <= set(
        rows["fatalities"][0]
    )
    # 1996 is the first year the locations table holds rows at all.
    assert rows["locations"] and {"EVENT_ID", "LOCATION_INDEX", "LATITUDE", "LONGITUDE"} <= set(
        rows["locations"][0]
    )
    (before,) = fetch(
        dataset, build_query(start="1995-01-01", end="1995-12-31", table="locations"), root=tmp_path
    )
    with gzip.open(before.path, "rt", encoding="utf-8", newline="") as stream:
        assert list(csv.DictReader(stream)) == []
