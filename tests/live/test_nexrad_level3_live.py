"""Hits the live unidata-nexrad-level3 bucket. Run with ``just test-live``."""

from pathlib import Path

import pytest

from usdata import fetch_asset
from usdata.providers import load_adapter
from usdata.query import build_query
from usdata.readers import UnsupportedFormat
from usdata.registry import default_registry

pytestmark = pytest.mark.live


def test_list_and_fetch_one_small_product(tmp_path: Path) -> None:
    ds = default_registry().get("noaa:nexrad-level3")
    adapter = load_adapter(ds)
    # Echo tops are about 1.5 kB each; keep the live download cheap.
    assets = adapter.list_assets(
        build_query(site="KTLX", products="EET", start="2024-05-06T20:00Z", end="2024-05-06T20:30Z")
    )
    assert assets and all(a.id.startswith("TLX_EET_2024_05_06_20_") for a in assets)
    assert all(a.size and a.size < 10_000 for a in assets)
    got = fetch_asset(ds, assets[0], root=tmp_path)
    assert got.path.stat().st_size == assets[0].size
    assert got.provenance.checksum.startswith("sha256:")
    with pytest.raises(UnsupportedFormat, match="Py-ART"):
        got.open()


def test_two_products_from_a_point_query() -> None:
    ds = default_registry().get("noaa:nexrad-level3")
    adapter = load_adapter(ds)
    assets = adapter.list_assets(
        build_query(
            lat=35.39,
            lon=-97.60,
            radius_km=10,
            products="N0B,NMD",
            start="2024-05-06T20:30Z",
            end="2024-05-06T21:00Z",
        )
    )
    codes = {a.id.split("_")[1] for a in assets}
    assert codes == {"N0B", "NMD"}
    assert all(a.id.startswith("TLX_") for a in assets)
