from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata.cli import app
from usdata.fetch import ChecksumMismatch
from usdata.protocols.erddap import GridSlice, griddap_url
from usdata.providers.base import QueryError
from usdata.providers.noaa.coastwatch import BASE, DATASET, CoastwatchSst
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

INFO_URL = f"{BASE}/info/{DATASET}/index.csv"
GRID_URL = f"{BASE}/griddap/{DATASET}.csv"
INFO = (Path(__file__).resolve().parents[1] / "fixtures/coastwatch-info.csv").read_text()
TIMES = "time\nUTC\n2024-05-06T12:00:00Z\n2024-05-08T12:00:00Z\n"
CSV = (
    b"time,latitude,longitude,analysed_sst\nUTC,degrees_north,degrees_east,degree_C\n"
    b"2024-05-06T12:00:00Z,30.025,-80.075,26.85\n"
)


def query(**overrides):
    values: dict[str, Any] = dict(
        bbox=(-80.08, 30.02, -80.02, 30.08), start="2024-05-06T12:00Z", end="2024-05-08T12:00Z"
    )
    return build_query(**(values | overrides))


@pytest.fixture
def adapter():
    with CoastwatchSst(default_registry().get("noaa:coastwatch-sst")) as provider:
        yield provider


@pytest.mark.parametrize(
    "override",
    [
        {"bbox": None},
        {"start": None},
        {"end": None},
        {"variables": ["typo"]},
        {"format": "nc"},
        {"stride": 0},
        {"stride": -1},
        {"stride": True},
        {"stride": 1.5},
        {"stride": "oops"},
    ],
)
def test_invalid_constraints_fail_before_http(adapter, override) -> None:
    with pytest.raises(QueryError):
        adapter.list_assets(query(**override))


def test_subset_uses_available_times_and_contained_grid_centers(adapter) -> None:
    with respx.mock() as mock:
        mock.get(INFO_URL).respond(200, text=INFO)
        mock.get(GRID_URL + "?time").respond(200, text=TIMES)
        (asset,) = adapter.list_assets(query())
    url = unquote(asset.href)
    assert "analysed_sst[(2024-05-06T12:00:00Z):1:(2024-05-08T12:00:00Z)]" in url
    assert "[(30.025):1:(30.075)][(-80.075):1:(-80.025)]" in url
    assert asset.bbox and asset.bbox.west == -80.075
    assert asset.time and asset.time.start == datetime(2024, 5, 6, 12, tzinfo=UTC)
    assert asset.media_type == "text/csv"


@pytest.mark.parametrize(
    "override",
    [
        {"start": "2020-01-01", "end": "2020-01-02"},
        {"start": "2024-05-07", "end": "2024-05-08"},
        {"start": "2027-01-01", "end": "2027-01-02"},
    ],
)
def test_empty_time_intersections_do_not_snap_to_other_days(adapter, override) -> None:
    with respx.mock() as mock:
        mock.get(INFO_URL).respond(200, text=INFO)
        mock.get(GRID_URL + "?time").respond(200, text=TIMES)
        assert adapter.list_assets(query(**override)) == []


def test_box_without_grid_centers_returns_empty_without_http(adapter) -> None:
    assert adapter.list_assets(query(bbox=(0, 0, 0.01, 0.01))) == []


def test_variables_stride_and_stable_query_ids(adapter) -> None:
    with respx.mock() as mock:
        mock.get(INFO_URL).respond(200, text=INFO)
        mock.get(GRID_URL + "?time").respond(200, text=TIMES)
        (a,) = adapter.list_assets(query(variables=["mask", "analysed_sst"], stride="2"))
        (b,) = adapter.list_assets(query(variables=["analysed_sst", "mask", "mask"], stride=2))
    assert a == b
    assert "[(30.025):2:(30.025)]" in unquote(a.href)
    assert a.bbox and a.bbox.north == 30.025


def test_large_requests_are_rejected(adapter) -> None:
    with respx.mock() as mock:
        mock.get(INFO_URL).respond(200, text=INFO)
        mock.get(GRID_URL + "?time").respond(200, text=TIMES)
        with pytest.raises(QueryError, match="1,000,000"):
            adapter.list_assets(query(bbox=(-180, -90, 180, 90)))


@pytest.mark.parametrize(
    "info,times",
    [
        ("broken", TIMES),
        (INFO.replace("nValues=3600", "nValues=1800"), TIMES),
        (INFO.replace("time, latitude, longitude", "longitude, latitude, time"), TIMES),
        (INFO, "time\nUTC\nnot-a-date\n"),
        (INFO, "time\nUTC\n2024-05-08T12:00:00Z\n2024-05-06T12:00:00Z\n"),
    ],
)
def test_changed_or_malformed_metadata_is_an_upstream_error(adapter, info, times) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(INFO_URL).respond(200, text=info)
        mock.get(GRID_URL + "?time").respond(200, text=times)
        with pytest.raises(httpx.DecodingError):
            adapter.list_assets(query())


def test_manifest_cache_restore_checksum_and_cli(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: sst
sources:
  - dataset: noaa:coastwatch-sst
    bbox: {west: -80.08, south: 30.02, east: -80.02, north: 30.08}
    start: 2024-05-06T12:00:00Z
    end: 2024-05-08T12:00:00Z
""")
    with respx.mock() as mock:
        mock.get(INFO_URL).respond(200, text=INFO)
        mock.get(GRID_URL + "?time").respond(200, text=TIMES)
        mock.get(GRID_URL).respond(200, content=CSV)
        first = pull(manifest, root=tmp_path / "cache")
    # Cached/locked operations must not request metadata or coordinate axes.
    with respx.mock() as mock:
        assert pull(manifest, root=tmp_path / "cache").fetched[0].from_cache
        assert verify(manifest, root=tmp_path / "cache") == []
    path = first.fetched[0].path
    path.unlink()
    with respx.mock() as mock:
        mock.get(first.fetched[0].asset.href).respond(200, content=CSV)
        result = CliRunner().invoke(
            app, ["pull", str(manifest), "--cache-dir", str(tmp_path / "cache")]
        )
    assert result.exit_code == 0 and "fetched" in result.output
    path.write_bytes(b"local corruption")
    with respx.mock() as mock:
        mock.get(first.fetched[0].asset.href).respond(200, content=b"upstream changed")
        with pytest.raises(ChecksumMismatch):
            pull(manifest, root=tmp_path / "cache")
    assert path.read_bytes() == b"local corruption"


def test_griddap_builder_rejects_url_injection() -> None:
    for dataset in ("../other", "sst?secret", "sst#part"):
        with pytest.raises(ValueError):
            griddap_url(BASE, dataset, ["sst"], [GridSlice(1, 2)])
    with pytest.raises(ValueError):
        griddap_url(BASE, DATASET, ["sst&evil"], [GridSlice(1, 2)])
    with pytest.raises(ValueError):
        griddap_url(BASE, DATASET, ["sst"], [GridSlice(float("nan"), 2)])
