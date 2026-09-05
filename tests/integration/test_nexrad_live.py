"""Hits the live unidata-nexrad-level2 bucket. Run with ``just test-integration``."""

from pathlib import Path

import pytest

from usdata.fetch import fetch_asset
from usdata.providers import load_adapter
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.integration


def test_list_and_fetch_one_legacy_scan(tmp_path: Path) -> None:
    ds = default_registry().get("noaa:nexrad-level2")
    adapter = load_adapter(ds)
    # 1995 scans are small (~1 MB); keep the live download cheap.
    assets = adapter.list_assets(
        build_query(site="KTLX", start="1995-05-06T00:00", end="1995-05-06T00:15")
    )
    assert assets and all(a.id.startswith("KTLX19950506_") for a in assets)
    got = fetch_asset(ds, assets[0], root=tmp_path)
    assert got.path.stat().st_size == assets[0].size
    assert got.provenance.checksum.startswith("sha256:")


def test_point_query_selects_ktlx() -> None:
    ds = default_registry().get("noaa:nexrad-level2")
    adapter = load_adapter(ds)
    assets = adapter.list_assets(
        build_query(
            lat=35.39, lon=-97.60, radius_km=10, start="2024-05-06T20:00", end="2024-05-06T20:30"
        )
    )
    assert assets and all(a.id.startswith("KTLX20240506_20") for a in assets)
