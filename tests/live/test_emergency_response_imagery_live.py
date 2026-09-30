"""NGS emergency response imagery: the smallest tile by footprint, and the refusals, live."""

from pathlib import Path

import pytest

from usdata.providers import QueryError, load_adapter
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.live

DATASET = "noaa:emergency-response-imagery"
# The smallest GeoTIFF in the bucket when probed on 2026-09-29: 148,047 bytes.
SMALLEST = "2022_Pre_Event/CB2201a_OB_N_RGB/CB2201a_OB_NC0644930w174545n.tif"


def test_the_smallest_tile_selected_by_its_footprint_and_restored(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(f"""name: smallest-eri-tile
sources:
  - dataset: {DATASET}
    bbox: {{west: -64.82, south: 17.76, east: -64.82, north: 17.76}}
    params: {{event: 2022_Pre_Event, collection: CB2201a_OB_N_RGB}}
""")
    result = pull(manifest, root=tmp_path / "first")
    (item,) = result.fetched
    assert item.asset.id == SMALLEST
    assert item.asset.bbox is not None and item.asset.bbox.contains_point(17.76, -64.82)
    assert item.path.stat().st_size == item.asset.size
    assert item.path.read_bytes()[:4] in (b"II*\x00", b"II+\x00")
    restored = pull(manifest, root=tmp_path / "empty")
    assert restored.from_lockfile and not restored.fetched[0].from_cache
    assert restored.lockfile == result.lockfile
    assert verify(manifest, root=tmp_path / "empty") == []


def test_joplin_utm_tiles_are_placed_in_their_folder_zone() -> None:
    with load_adapter(default_registry().get(DATASET)) as adapter:
        assets = adapter.list_assets(
            build_query(event="2011_Joplin_Tornado", bbox=(-94.43, 37.03, -94.42, 37.035))
        )
    # 372500 E 4100000 N, zone 15, is 94.4336°W 37.0376°N: the box sits just south-east of
    # it. Only the 26 May flight has a tile there.
    assert [asset.id for asset in assets] == [
        "2011_Joplin_Tornado/may26JPEGtiles_UTMZone15/may26C372500e4100000n.tif"
    ]
    assert assets[0].properties == {"utm_zone": "15"}


def test_an_event_of_individual_frames_refuses_a_bbox() -> None:
    with (
        load_adapter(default_registry().get(DATASET)) as adapter,
        pytest.raises(QueryError, match="state no footprint"),
    ):
        adapter.list_assets(build_query(event="2005_Hurricane_Wilma", bbox=(-82, 25, -80, 27)))


def test_a_misspelt_event_is_answered_with_the_bucket_events() -> None:
    with (
        load_adapter(default_registry().get(DATASET)) as adapter,
        pytest.raises(QueryError, match="did you mean 2020_Nashville_Tornado"),
    ):
        adapter.list_assets(build_query(event="2020_Nashvile_Tornado"))
