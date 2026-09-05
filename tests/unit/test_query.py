from datetime import UTC, datetime

import pytest

from usdata.models import BBox
from usdata.query import UnknownPlace, build_query, parse_datetime, resolve_place


def test_resolve_place_by_name_and_alias() -> None:
    assert resolve_place("Oklahoma") == resolve_place("ok")
    assert resolve_place("oklahoma").contains_point(35.47, -97.52)
    with pytest.raises(UnknownPlace):
        resolve_place("Atlantis")


def test_parse_datetime_defaults_to_utc() -> None:
    assert parse_datetime("2024-05-06") == datetime(2024, 5, 6, tzinfo=UTC)
    assert parse_datetime("2024-05-06T20:00") == datetime(2024, 5, 6, 20, tzinfo=UTC)
    assert parse_datetime(None) is None


def test_build_query_from_location_and_dates() -> None:
    q = build_query("radar", location="OK", start="2024-05-06", end="2024-05-07", site="KTLX")
    assert q.text == "radar"
    assert q.bbox is not None and q.bbox.contains_point(35.47, -97.52)
    assert q.time is not None and q.time.start is not None and q.time.start.day == 6
    assert q.params == {"site": "KTLX"}


def test_build_query_from_point_and_tuple() -> None:
    q = build_query(lat=35.47, lon=-97.52, radius_km=10)
    assert q.bbox is not None and q.bbox.contains_point(35.47, -97.52)
    q2 = build_query(bbox=(-100, 30, -90, 40))
    assert q2.bbox == BBox(west=-100, south=30, east=-90, north=40)


def test_build_query_rejects_conflicting_spatial_args() -> None:
    with pytest.raises(ValueError):
        build_query(location="ok", lat=1, lon=1)
    with pytest.raises(ValueError):
        build_query(lat=1)
