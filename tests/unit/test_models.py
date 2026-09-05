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


def test_time_range_overlap_with_open_bounds() -> None:
    t = lambda y: datetime(y, 1, 1, tzinfo=UTC)  # noqa: E731
    open_start = TimeRange(start=t(1991))
    assert open_start.overlaps(TimeRange(start=t(2020), end=t(2021)))
    assert not open_start.overlaps(TimeRange(end=t(1990)))
    assert TimeRange().overlaps(TimeRange(start=t(2000), end=t(2001)))
    with pytest.raises(ValidationError):
        TimeRange(start=t(2001), end=t(2000))


def test_dataset_id_must_match_provider() -> None:
    def make(id: str, adapter: str | None = "m:C", status: Status = Status.STUB) -> Dataset:
        return Dataset(
            id=id,
            provider="noaa",
            title="x",
            protocol=Protocol.HTTP,
            adapter=adapter,
            status=status,
        )

    make("noaa:thing")
    with pytest.raises(ValidationError):
        make("usgs:thing")
    with pytest.raises(ValidationError):
        make("noaa:")
    with pytest.raises(ValidationError):
        make("noaa:thing", adapter="bad")


def test_dataset_status_and_adapter_agree() -> None:
    def make(status: Status, adapter: str | None) -> Dataset:
        return Dataset(
            id="noaa:x",
            provider="noaa",
            title="x",
            protocol=Protocol.HTTP,
            status=status,
            adapter=adapter,
        )

    make(Status.PLANNED, None)
    make(Status.AVAILABLE, "m:C")
    with pytest.raises(ValidationError, match="must not name an adapter"):
        make(Status.PLANNED, "m:C")
    with pytest.raises(ValidationError, match="need adapter"):
        make(Status.STUB, None)
