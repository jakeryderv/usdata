"""Small live Damage Assessment Toolkit queries: one track pinned and restored, and one photo."""

import json
from pathlib import Path

import pytest

from usdata import build_query, fetch, fetch_asset, get
from usdata.providers import load_adapter
from usdata.pull import pull, verify

pytestmark = pytest.mark.live


def test_the_barnsdall_ef4_track_pinned_at_an_archive_moment(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: barnsdall-track
sources:
  - name: track
    dataset: noaa:nws-damage-surveys
    start: 2024-05-06T12:00Z
    end: 2024-05-07T12:00Z
    params: {layer: lines, office: TSA, efscale: EF4, as_of: "2026-09-29T00:00Z"}
""")
    result = pull(manifest, root=tmp_path / "cache")
    item = result.one("track")
    assert item.asset.properties == {"layer": "lines", "as_of": "2026-09-29T00:00:00Z"}
    (feature,) = json.loads(item.path.read_text())["features"]
    assert feature["geometry"]["type"] == "LineString"
    attributes = feature["properties"]
    # 9:12 PM CDT on 6 May is 02:12 UTC on 7 May; stormdate and starttime agree on tracks.
    assert attributes["starttime"] == attributes["stormdate"] == 1715047920000
    assert (attributes["efscale"], attributes["wfo"]) == ("EF4", "TSA")
    item.path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and not restored.one("track").from_cache
    assert verify(manifest, root=tmp_path / "cache") == []


def test_the_archive_holds_fewer_tracks_two_days_after_the_outbreak(tmp_path: Path) -> None:
    dataset = get("noaa:nws-damage-surveys")
    start, end = "2024-05-06T12:00Z", "2024-05-07T12:00Z"
    archived = build_query(start=start, end=end, layer="lines", as_of="2024-05-08T00:00Z")
    (then,) = fetch(dataset, archived, root=tmp_path)
    (now,) = fetch(dataset, build_query(start=start, end=end, layer="lines"), root=tmp_path)
    surveyed_then = json.loads(then.path.read_text())["features"]
    surveyed_now = json.loads(now.path.read_text())["features"]
    assert 0 < len(surveyed_then) < len(surveyed_now)


def test_an_older_photo_and_its_thumbnail_are_both_listed(tmp_path: Path) -> None:
    query = build_query(
        start="2011-04-27",
        end="2011-04-28",
        bbox=(-87.737, 34.328, -87.736, 34.329),
        efscale="EF5",
    )
    with load_adapter(get("noaa:nws-damage-photos")) as adapter:
        assets = adapter.list_assets(query)
    by_point = {a.id: a for a in assets if a.properties["point_objectid"] == "25520"}
    photo, thumbnail = (
        by_point["nws_damage_photo_25520_15668.jpg"],
        by_point["nws_damage_photo_25520_20831.jpg"],
    )
    assert photo.properties["name"] == thumbnail.properties["name"]
    assert photo.size and thumbnail.size and thumbnail.size < photo.size / 10
    item = fetch_asset(get("noaa:nws-damage-photos"), thumbnail, root=tmp_path)
    data = item.path.read_bytes()
    assert data[:3] == b"\xff\xd8\xff" and len(data) == thumbnail.size
