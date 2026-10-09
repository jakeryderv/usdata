"""Hits the live unidata-nexrad-level2 bucket. Run with ``just test-integration``."""

from pathlib import Path

import pytest

from usdata import fetch_asset
from usdata.providers import load_adapter
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.live


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


def test_a_sails_volume_lists_the_lowest_angle_eight_times(tmp_path: Path) -> None:
    pytest.importorskip("xradar")
    ds = default_registry().get("noaa:nexrad-level2")
    adapter = load_adapter(ds)
    assets = adapter.list_assets(
        build_query(site="KTLX", start="2024-05-07T02:11:23Z", end="2024-05-07T02:11:23Z")
    )
    (asset,) = [a for a in assets if a.id == "KTLX20240507_021123_V06"]
    volume = fetch_asset(ds, asset, root=tmp_path).inspect().nexrad
    assert volume is not None and volume.vcp == 212 and len(volume.sweeps) == 23
    lowest = [s for s in volume.sweeps if round(s.fixed_angle, 2) == 0.48]
    # Four split cuts at 0.5 degrees, three of them SAILS rescans: velocity on every other one.
    assert [s.index for s in lowest] == [0, 1, 4, 5, 9, 10, 16, 17]
    assert [s.index for s in lowest if "VRADH" in s.moments] == [1, 5, 10, 17]
    assert [s.sails for s in lowest] == [False, False] + [True] * 6
