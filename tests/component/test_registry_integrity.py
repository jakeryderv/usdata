from pathlib import Path

import pytest

from usdata import get, search
from usdata.providers.noaa.sites import all_sites
from usdata.registry import Registry

ROOT = Path(__file__).resolve().parents[2]

# Radars beyond the antimeridian from the NEXRAD extents. A BBox cannot wrap, so one box
# holding them would span every longitude; the Level II guide names them instead.
NEXRAD_OUTSIDE_EXTENT = {"PGUA", "RKJK", "RKSG", "RODN"}


def test_registry_infers_multiple_domains() -> None:
    datasets = [get("noaa:ghcn-daily"), get("noaa:nexrad-level2")]
    registry = Registry(datasets)
    assert {domain.id for domain in registry.domains()} == {d.domain for d in datasets}


@pytest.mark.parametrize("dataset_id", ["noaa:nexrad-level2", "noaa:nexrad-level3"])
def test_nexrad_extent_holds_every_bundled_radar_but_the_documented_ones(dataset_id) -> None:
    extent = get(dataset_id).spatial_extent
    assert extent is not None
    outside = {s.id for s in all_sites().values() if not extent.contains_point(s.lat, s.lon)}
    assert outside == NEXRAD_OUTSIDE_EXTENT
    guide = (ROOT / "docs/providers/noaa-nexrad.md").read_text(encoding="utf-8")
    assert all(f"`{site}`" in guide for site in NEXRAD_OUTSIDE_EXTENT)
    # A radar inside the extent is found by searching at its location.
    lajes = all_sites()["LPLA"]
    found = {r.dataset.id for r in search("radar", lat=lajes.lat, lon=lajes.lon)}
    assert dataset_id in found
