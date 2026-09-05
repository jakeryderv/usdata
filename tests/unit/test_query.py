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


def test_counties_fips_and_qualified_names() -> None:
    assert resolve_place("40") == resolve_place("Oklahoma")
    county = resolve_place("Cleveland County, OK")
    assert county == resolve_place("40027") == resolve_place("Cleveland, Oklahoma")
    assert county == resolve_place(" cleveland  county ,ok ")
    assert county.contains_point(35.22, -97.44)
    assert resolve_place("09110") == resolve_place("Capitol Planning Region, CT")
    assert resolve_place("AS") == resolve_place("American Samoa")
    assert resolve_place("GU") == resolve_place("66")
    assert resolve_place("MP") == resolve_place("69")
    assert resolve_place("PR") == resolve_place("72")
    assert resolve_place("VI") == resolve_place("78")


def test_ambiguous_counties_do_not_choose_a_silent_match() -> None:
    from usdata.query import AmbiguousPlace

    with pytest.raises(AmbiguousPlace, match="state or FIPS"):
        resolve_place("Washington County")
    with pytest.raises(AmbiguousPlace):
        resolve_place("Fairfax, VA")
    assert resolve_place("Fairfax County, VA") != resolve_place("Fairfax city, VA")
    # A state name takes precedence over a county-equivalent of the same name.
    assert resolve_place("District of Columbia") == resolve_place("11")
    with pytest.raises(UnknownPlace):
        resolve_place("1")  # Leading zero required: this must be '01'.


def test_census_coverage_and_conservative_antimeridian_boxes() -> None:
    import csv
    import hashlib
    import io
    import json
    from importlib import resources

    data = resources.files("usdata.data")
    raw = (data / "places.csv").read_bytes()
    metadata = json.loads((data / "places.sources.json").read_text(encoding="utf-8"))
    assert metadata["vintage"] == "2025"
    assert hashlib.sha256(raw).hexdigest() == metadata["csv_sha256"]
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    assert sum(r["kind"] == "state" for r in rows) == 56
    assert sum(r["kind"] == "county" for r in rows) == 3235
    assert len({r["geoid"] for r in rows}) == len(rows)
    for row in rows:
        box = resolve_place(row["geoid"])
        assert box.west < box.east and box.south < box.north
    for name in ("Alaska", "Aleutians West Census Area, AK"):
        box = resolve_place(name)
        assert box.east - box.west > 350
