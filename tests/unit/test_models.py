from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from usdata.models import BBox, Dataset, Protocol, Status, TimeRange


def test_bbox_rejects_inverted_bounds() -> None:
    with pytest.raises(ValidationError):
        BBox(west=10, south=0, east=0, north=1)
    with pytest.raises(ValidationError):
        BBox(west=0, south=10, east=1, north=0)


def test_bbox_intersects_and_contains() -> None:
    a = BBox(west=-100, south=30, east=-90, north=40)
    assert a.intersects(BBox(west=-95, south=35, east=-80, north=45))
    assert not a.intersects(BBox(west=-80, south=35, east=-70, north=45))
    assert a.contains_point(35, -95)
    assert not a.contains_point(35, -85)


def test_bbox_from_point_is_centered() -> None:
    box = BBox.from_point(35.0, -97.0, radius_km=111.0)
    assert box.south == pytest.approx(34.0)
    assert box.north == pytest.approx(36.0)
    assert box.west < -97.0 < box.east


@pytest.mark.parametrize("lat", [-91, 91, float("nan"), float("inf"), -float("inf")])
def test_bbox_from_point_rejects_invalid_latitude_before_clipping(lat: float) -> None:
    with pytest.raises(ValueError, match="lat must be finite and between"):
        BBox.from_point(lat, 0, radius_km=200)


@pytest.mark.parametrize("lon", [-181, 181, float("nan"), float("inf"), -float("inf")])
def test_bbox_from_point_rejects_invalid_longitude_before_clipping(lon: float) -> None:
    with pytest.raises(ValueError, match="lon must be finite and between"):
        BBox.from_point(0, lon, radius_km=200)


@pytest.mark.parametrize("radius", [-1, float("nan"), float("inf"), -float("inf")])
def test_bbox_from_point_rejects_invalid_radius(radius: float) -> None:
    with pytest.raises(ValueError, match="radius_km must be finite and nonnegative"):
        BBox.from_point(35, -97, radius_km=radius)


@pytest.mark.parametrize("lat, lon", [(-90, -180), (90, 180), (35, -97)])
def test_bbox_from_point_accepts_boundaries_and_zero_radius(lat: float, lon: float) -> None:
    assert BBox.from_point(lat, lon).as_tuple() == (lon, lat, lon, lat)
    assert BBox.from_point(lat, lon, radius_km=200).contains_point(lat, lon)


def test_time_range_overlap_with_open_bounds() -> None:
    t = lambda y: datetime(y, 1, 1, tzinfo=UTC)  # noqa: E731
    open_start = TimeRange(start=t(1991))
    assert open_start.overlaps(TimeRange(start=t(2020), end=t(2021)))
    assert not open_start.overlaps(TimeRange(end=t(1990)))
    assert TimeRange().overlaps(TimeRange(start=t(2000), end=t(2001)))
    with pytest.raises(ValidationError):
        TimeRange(start=t(2001), end=t(2000))


def _dataset(**overrides: object) -> Dataset:
    base: dict[str, object] = {
        "id": "noaa:thing",
        "provider": "noaa",
        "title": "x",
        "protocol": Protocol.HTTP,
        "domain": "climate",
        "status": Status.PLANNED,
        "target": "later",
        "adapter": None,
    }
    return Dataset.model_validate({**base, **overrides})


def test_dataset_id_must_match_provider() -> None:
    assert _dataset().name == "thing"
    with pytest.raises(ValidationError):
        _dataset(id="usgs:thing")
    with pytest.raises(ValidationError):
        _dataset(id="noaa:")
    with pytest.raises(ValidationError):
        _dataset(adapter="bad")


def test_dataset_status_adapter_and_versions_agree() -> None:
    assert _dataset().version_label == "target later"
    assert _dataset(target="0.3").version_label == "target 0.3"
    shipped = _dataset(status=Status.AVAILABLE, target=None, since="0.2", adapter="m:C")
    assert shipped.version_label == "since 0.2"
    with pytest.raises(ValidationError, match="must not name an adapter"):
        _dataset(adapter="m:C")
    with pytest.raises(ValidationError, match="need adapter"):
        _dataset(status=Status.AVAILABLE, target=None, since="0.2")
    with pytest.raises(ValidationError, match="need a target"):
        _dataset(target=None)
    with pytest.raises(ValidationError, match="shipped in"):
        _dataset(status=Status.AVAILABLE, target=None, adapter="m:C")
    with pytest.raises(ValidationError, match="no target"):
        _dataset(status=Status.AVAILABLE, since="0.2", adapter="m:C")
    with pytest.raises(ValidationError, match="minor version"):
        _dataset(target="v0.4")
