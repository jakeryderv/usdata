from datetime import UTC, date, datetime

import pytest

from usdata.models import BBox, TimeRange
from usdata.query import (
    UnknownPlace,
    build_query,
    find_place,
    legacy_counties,
    parse_datetime,
    resolve_place,
)


def test_resolve_place_by_name_and_alias() -> None:
    assert resolve_place("Oklahoma") == resolve_place("ok")
    assert resolve_place("oklahoma").contains_point(35.47, -97.52)
    with pytest.raises(UnknownPlace):
        resolve_place("Atlantis")


def test_parse_datetime_defaults_to_utc() -> None:
    assert parse_datetime("2024-05-06") == datetime(2024, 5, 6, tzinfo=UTC)
    assert parse_datetime("2024-05-06T20:00") == datetime(2024, 5, 6, 20, tzinfo=UTC)
    assert parse_datetime(None) is None


def test_bare_end_date_runs_to_the_last_instant_of_its_day() -> None:
    last = datetime(2024, 5, 7, 23, 59, 59, 999999, tzinfo=UTC)
    assert parse_datetime("2024-05-07", end=True) == last
    assert parse_datetime(" 2024-05-07 ", end=True) == last
    assert parse_datetime(date(2024, 5, 7), end=True) == last
    # Every date-only spelling is a whole day, not only the extended one.
    for spelling in ("20240507", "2024-W19-2", "2024W192"):
        assert parse_datetime(spelling, end=True) == last, spelling
        assert parse_datetime(spelling) == datetime(2024, 5, 7, tzinfo=UTC), spelling
    assert build_query(start="2024-01-10", end="20240115").time == (
        build_query(start="2024-01-10", end="2024-01-15").time
    )
    # A datetime is taken as given on either bound, and a bare start is still midnight.
    assert parse_datetime("2024-05-07T00:00Z", end=True) == datetime(2024, 5, 7, tzinfo=UTC)
    assert parse_datetime(datetime(2024, 5, 7), end=True) == datetime(2024, 5, 7, tzinfo=UTC)
    assert parse_datetime(date(2024, 5, 7)) == datetime(2024, 5, 7, tzinfo=UTC)
    whole_day = build_query(start="2024-05-07", end="2024-05-07").time
    assert whole_day == TimeRange(start=datetime(2024, 5, 7, tzinfo=UTC), end=last)
    assert whole_day == build_query(start=date(2024, 5, 7), end=date(2024, 5, 7)).time
    assert (
        whole_day == build_query(start="2024-05-07T00:00Z", end="2024-05-07T23:59:59.999999Z").time
    )


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


def test_build_query_rejects_invalid_point_before_clipping() -> None:
    with pytest.raises(ValueError, match="lat must be finite and between"):
        build_query(lat=91, lon=0, radius_km=200)


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


LEGACY_CT = {
    "09001": "Fairfield",
    "09003": "Hartford",
    "09005": "Litchfield",
    "09007": "Middlesex",
    "09009": "New Haven",
    "09011": "New London",
    "09013": "Tolland",
    "09015": "Windham",
}


@pytest.mark.parametrize(("geoid", "name"), LEGACY_CT.items())
def test_connecticuts_legacy_counties_resolve_beside_its_planning_regions(geoid, name) -> None:
    place = build_query(location=f"{name} County, CT").place
    assert place is not None
    assert (place.kind, place.geoid, place.state) == ("county", geoid, "CT")
    assert place.label == f"{name} County, CT"
    assert find_place(geoid) == find_place(f"{name}, Connecticut")
    state, county = resolve_place("Connecticut"), resolve_place(geoid)
    assert state.west <= county.west < county.east <= state.east
    assert state.south <= county.south < county.north <= state.north
    # A legacy county is what the old-code sources want, so it maps to nothing further.
    assert legacy_counties(place) == ()


def test_a_planning_region_lists_the_legacy_counties_it_shares_a_town_with() -> None:
    capitol, _ = find_place("Capitol Planning Region, CT")
    assert capitol.geoid == "09110" and capitol.label == "Capitol Planning Region, CT"
    assert [c.geoid for c in legacy_counties(capitol)] == ["09003", "09013"]
    naugatuck = legacy_counties(find_place("09140")[0])
    assert [c.label for c in naugatuck] == [
        "Fairfield County, CT",
        "Hartford County, CT",
        "Litchfield County, CT",
        "New Haven County, CT",
    ]
    regions = [find_place(f"09{code}")[0] for code in range(110, 200, 10)]
    overlapped = {county.geoid for region in regions for county in legacy_counties(region)}
    assert overlapped == set(LEGACY_CT)
    for region in regions:
        for county in legacy_counties(region):
            assert resolve_place(region.geoid).intersects(resolve_place(county.geoid))
    for other in ("Connecticut", "Osage County, OK", "Fairfield County, OH"):
        assert legacy_counties(find_place(other)[0]) == ()


def test_legacy_county_names_do_not_collide_with_other_places() -> None:
    from usdata.query import AmbiguousPlace

    # Unique names now resolve bare; shared ones stay ambiguous rather than choose one.
    assert resolve_place("Hartford County") == resolve_place("09003")
    with pytest.raises(AmbiguousPlace, match="Fairfield County, CT"):
        resolve_place("Fairfield County")
    assert resolve_place("Fairfield County, OH") != resolve_place("Fairfield County, CT")
    assert find_place("CT")[0].kind == "state"


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


def test_census_coverage_and_antimeridian_clipped_boxes() -> None:
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
    # Connecticut's counties before 2022, from the last vintage that held them.
    legacy = [r["geoid"] for r in rows if r["kind"] == "legacy_county"]
    assert legacy == [f"09{code:03d}" for code in range(1, 16, 2)]
    assert metadata["connecticut_legacy_counties"]["vintage"] == "2021"
    sources = metadata["connecticut_legacy_counties"]["sources"]
    assert [s["url"].rsplit("/", 1)[1] for s in sources] == [
        "cb_2021_us_county_500k.zip",
        "ct_cou_to_cousub_crosswalk.txt",
    ]
    linked = {r["geoid"] for r in rows if r["legacy_counties"]}
    assert linked == {f"09{code}" for code in range(110, 200, 10)}
    assert len({r["geoid"] for r in rows}) == len(rows)
    for row in rows:
        box = resolve_place(row["geoid"])
        assert box.west < box.east and box.south < box.north
        assert box.east - box.west < 180, row["geoid"]
    # Places split by 180 degrees keep their western part; the dropped islands are recorded.
    clipped = metadata["antimeridian"]["clipped"]
    assert {clip["geoid"] for clip in clipped} == {"02", "02016"}
    assert all(clip["dropped_box"][0] > 170 for clip in clipped)
    alaska = build_query(location="Alaska").bbox
    assert alaska is not None
    assert (alaska.west, alaska.east) == (-179.146711, -129.974167)
    assert alaska.contains_point(61.2, -149.9) and not alaska.contains_point(
        56.0, 160.0
    )  # Kamchatka
    assert resolve_place("Aleutians West Census Area, AK").east < -160


def test_a_location_keeps_the_place_it_resolved_beside_its_box() -> None:
    county = build_query(location="Osage County, OK")
    assert county.place is not None
    assert (county.place.kind, county.place.geoid) == ("county", "40113")
    assert (county.place.state_fips, county.place.county_fips) == ("40", "113")
    assert county.place.state == "OK"
    assert county.place.label == "Osage County, OK"
    assert county.bbox == resolve_place("40113")
    state = build_query(location="ok")
    assert state.place is not None
    assert (state.place.kind, state.place.geoid, state.place.label) == ("state", "40", "Oklahoma")
    assert (state.place.state_fips, state.place.county_fips) == ("40", None)
    assert state.place.state == "OK"
    # Every place the table holds carries a postal code, territories and the District included.
    assert find_place("Puerto Rico")[0].state == "PR"
    assert find_place("District of Columbia")[0].state == "DC"
    # However the place was spelled, it is the same place.
    assert build_query(location="40113").place == county.place
    assert find_place("Osage, Oklahoma") == (county.place, county.bbox)


def test_a_box_or_a_point_names_no_place() -> None:
    osage = resolve_place("Osage County, OK")
    assert build_query(bbox=osage).place is None
    assert build_query(lat=36.6, lon=-96.4).place is None
    assert build_query("rain").place is None
