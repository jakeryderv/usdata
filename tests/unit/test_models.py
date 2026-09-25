from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from usdata.models import (
    Asset,
    BBox,
    Capabilities,
    Dataset,
    Place,
    Protocol,
    Query,
    Status,
    TimeRange,
    Variable,
    describe_duration,
)


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


def _shipped(**overrides: object) -> Dataset:
    base: dict[str, object] = {
        "status": Status.AVAILABLE,
        "target": None,
        "since": "0.2",
        "adapter": "m:C",
        "summary": "A thing",
        "formats": ["CSV"],
    }
    return _dataset(**{**base, **overrides})


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
    assert _shipped().version_label == "since 0.2"
    with pytest.raises(ValidationError, match="must not name an adapter"):
        _dataset(adapter="m:C")
    with pytest.raises(ValidationError, match="need adapter"):
        _shipped(adapter=None)
    with pytest.raises(ValidationError, match="need a target"):
        _dataset(target=None)
    with pytest.raises(ValidationError, match="shipped in"):
        _shipped(since=None)
    with pytest.raises(ValidationError, match="no target"):
        _shipped(target="0.3")
    with pytest.raises(ValidationError, match="minor version"):
        _dataset(target="v0.4")


def test_available_datasets_state_what_they_deliver() -> None:
    assert _dataset().summary is None and _dataset().formats == []
    with pytest.raises(ValidationError, match="summary and at least one format"):
        _shipped(summary=None)
    with pytest.raises(ValidationError, match="summary and at least one format"):
        _shipped(formats=[])


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"summary": " "}, "summary must be a nonempty single line"),
        ({"selection": "one\ntwo"}, "selection must be a nonempty single line"),
        ({"inputs": ""}, "inputs must be a nonempty single line"),
        ({"formats": [" "]}, "formats entries must be a nonempty single line"),
        ({"reader": "polars"}, "reader must name a known extra"),
        ({"guide": "docs/guides/x.md"}, "guide must be a repository-relative path"),
        ({"guide": "docs/providers/../x.md"}, "guide must be a repository-relative path"),
        ({"guide": "/docs/providers/x.md"}, "guide must be a repository-relative path"),
        ({"guide": "docs/providers/x.txt"}, "guide must name a .md file"),
        ({"examples": ["docs/providers/x.md"]}, "examples entries must be a repository-relative"),
        ({"examples": ["examples/x.py"]}, "examples entries must name a"),
    ],
)
def test_usage_fields_are_validated(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        _shipped(**overrides)


def test_usage_fields_accept_the_shape_the_registry_uses() -> None:
    ds = _shipped(
        selection="Whole files by UTC start time",
        inputs="Both timestamps",
        reader="pandas",
        guide="docs/providers/noaa-thing.md",
        examples=["examples/thing/example.ipynb", "examples/thing/README.md"],
    )
    assert ds.reader == "pandas" and ds.guide == "docs/providers/noaa-thing.md"
    assert _shipped(reader=None).reader is None


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"resolution": {"spatial": "a\nb"}}, "resolution.spatial must be a nonempty single line"),
        ({"resolution": {"temporal": " "}}, "resolution.temporal must be a nonempty single line"),
        ({"update_frequency": "a\nb"}, "update_frequency must be a nonempty single line"),
        ({"latency": ""}, "latency must be a nonempty single line"),
        ({"citation": "a\nb"}, "citation must be a nonempty single line"),
        ({"terms": "http://example.gov/terms"}, "terms must be an https URL"),
        ({"terms": "example.gov/terms"}, "terms must be an https URL"),
        ({"variables": [{"name": " "}]}, "variable name must be a nonempty single line"),
        ({"variables": [{"name": "t", "units": "a\nb"}]}, "variable units must be a nonempty"),
        ({"variables": [{"name": "t"}, {"name": "t"}]}, "variables entries must have distinct"),
        ({"limits": {"max_window": "one day"}}, "max_window"),
        ({"limits": {"max_window": "PT0S"}}, "max_window must be a positive duration"),
        ({"limits": {"max_window": "-P1D"}}, "max_window must be a positive duration"),
    ],
)
def test_description_fields_are_validated(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        _shipped(**overrides)


def test_description_fields_accept_the_shape_the_registry_uses() -> None:
    ds = _shipped(
        resolution={"spatial": "3 km CONUS grid", "temporal": "Hourly runs"},
        update_frequency="Hourly",
        latency="About an hour behind the run",
        citation="NOAA, A Thing, accessed via usdata",
        terms="https://example.gov/terms",
        variables=[{"name": "cape", "units": "J/kg", "description": "Potential energy"}],
        limits={"max_window": "P1D"},
    )
    assert ds.resolution is not None and ds.resolution.spatial == "3 km CONUS grid"
    assert ds.limits is not None and ds.limits.max_window == timedelta(days=1)
    assert ds.variables[0].label == "cape (J/kg)"
    assert Variable(name="mask").label == "mask"
    assert _dataset().resolution is None and _dataset().variables == []
    assert _dataset().limits is None and _dataset().terms is None


@pytest.mark.parametrize(
    "value, expected",
    [
        (timedelta(days=1), "1 day"),
        (timedelta(days=31), "31 days"),
        (timedelta(hours=6), "6 hours"),
        (timedelta(minutes=1), "1 minute"),
        (timedelta(seconds=20), "20 seconds"),
    ],
)
def test_describe_duration_reads_as_words(value: timedelta, expected: str) -> None:
    assert describe_duration(value) == expected


def test_capabilities_name_partial_fetch_and_default_to_whole_files() -> None:
    assert _dataset().capabilities.partial_fetch is False
    assert _shipped(capabilities={"partial_fetch": True}).capabilities.partial_fetch is True


def test_a_place_holds_a_state_or_county_geoid_of_the_matching_length() -> None:
    county = Place(kind="county", geoid="40113", label="Osage County, OK", state="OK")
    assert (county.state_fips, county.county_fips, county.state) == ("40", "113", "OK")
    assert Place(kind="state", geoid="40", label="Oklahoma", state="OK").county_fips is None
    for kind, geoid in (("state", "40113"), ("county", "40"), ("county", "4011"), ("state", "OK")):
        with pytest.raises(ValidationError):
            Place.model_validate({"kind": kind, "geoid": geoid, "label": "x", "state": "OK"})


@pytest.mark.parametrize("state", ["ok", "Oklahoma", "O", "40", "", None])
def test_a_place_needs_its_states_two_letter_postal_code(state) -> None:
    with pytest.raises(ValidationError):
        Place.model_validate({"kind": "state", "geoid": "40", "label": "Oklahoma", "state": state})
    with pytest.raises(ValidationError, match="state"):
        Place.model_validate({"kind": "state", "geoid": "40", "label": "Oklahoma"})


def test_a_query_naming_a_place_must_carry_its_box() -> None:
    place = Place(kind="state", geoid="40", label="Oklahoma", state="OK")
    with pytest.raises(ValidationError, match="must carry that place's bbox"):
        Query(place=place)
    box = BBox(west=-103.0, south=33.6, east=-94.4, north=37.0)
    assert Query(place=place, bbox=box).place == place
    assert Query(bbox=box).place is None


def test_place_subset_is_a_separate_capability_that_defaults_to_false() -> None:
    assert Capabilities().place_subset is False
    keyed = Capabilities(place_subset=True)
    assert keyed.place_subset and not keyed.spatial_subset


def test_asset_properties_default_empty_and_older_json_parses() -> None:
    raw = {"id": "a", "dataset_id": "noaa:ghcn-daily", "href": "https://x/a", "protocol": "http"}
    assert Asset.model_validate(raw).properties == {}
    stated = Asset.model_validate({**raw, "properties": {"units": "metric"}})
    assert Asset.model_validate_json(stated.model_dump_json()) == stated
