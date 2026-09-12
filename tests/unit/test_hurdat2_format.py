"""Pure parsing rules for the HURDAT2 fixed-format text, without pandas or IO."""

from __future__ import annotations

import math

import pytest

from usdata._hurdat2 import COLUMNS, parse
from usdata.readers import Hurdat2FormatError

MODERN = (
    "AL092021,                IDA,      2,\n"
    "20210829, 1655, L, HU, 29.1N,  90.2W, 130,  931,  130,  110,   80,  110,   70,   60,"
    "   40,   60,   45,   35,   20,   30,   10\n"
    "20210830, 0600,  , TS, 30.6N,  90.8W,  65,  978,   80,  130,   80,   80,   50,   60,"
    "   30,   40,    0,    0,    0,    0,   25"
)
# A pre-2021 revision: no radius of maximum wind, and a terminating comma.
LEGACY = (
    "EP011949,            UNNAMED,      1,\n"
    "19490611, 0000,  , TS, 20.2N, 106.3W,  45" + ", -999" * 13 + ",\n"
)


def test_parses_every_documented_column_from_a_modern_record() -> None:
    columns = parse(MODERN)
    assert set(columns) == set(COLUMNS) and len(columns["storm_id"]) == 2
    assert columns["storm_id"] == ["AL092021", "AL092021"]
    assert columns["name"] == ["IDA", "IDA"]
    assert columns["time"][0].isoformat() == "2021-08-29T16:55:00+00:00"
    assert columns["record_identifier"] == ["L", None]
    assert columns["status"] == ["HU", "TS"]
    assert (columns["latitude"][0], columns["longitude"][0]) == (29.1, -90.2)
    assert (columns["max_wind_kt"][0], columns["min_pressure_mb"][0]) == (130.0, 931.0)
    assert columns["r34_ne_nm"][0] == 130.0 and columns["r64_nw_nm"][0] == 30.0
    assert columns["max_wind_radius_nm"] == [10.0, 25.0]


def test_accepts_pre_2021_lines_without_a_radius_of_maximum_wind() -> None:
    columns = parse(LEGACY)
    assert columns["storm_id"] == ["EP011949"]
    assert math.isnan(columns["max_wind_radius_nm"][0])
    assert all(math.isnan(columns[name][0]) for name in COLUMNS if name.endswith("_nm"))
    assert columns["max_wind_kt"] == [45.0] and math.isnan(columns["min_pressure_mb"][0])


def test_eastern_hemisphere_and_southern_coordinates_keep_their_sign() -> None:
    line = "20151231, 0000,  , TS, 12.5S, 179.8E,  45, 1000" + ", 0" * 13
    columns = parse(f"EP991949,              TEST,      1,\n{line}")
    assert (columns["latitude"][0], columns["longitude"][0]) == (-12.5, 179.8)


def test_longitudes_past_greenwich_in_the_unwrapped_0_360_convention_normalize() -> None:
    # Archived revisions carry a track crossing the prime meridian as 2.0W, 357.0W,
    # 351.0W: degrees west of Greenwich the long way round, so 357.0W is 3.0E.
    lines = [
        f"19660906, {hour}00,  , EX, 62.5N, {lon},  60, -999" + ", -999" * 13
        for hour, lon in (("12", "  2.0W"), ("18", "357.0W"), ("00", "299.0W"))
    ]
    columns = parse("AL061966, FAITH, 3,\n" + "\n".join(lines))
    assert columns["longitude"] == [-2.0, 3.0, 61.0]


def test_an_unwrapped_eastern_longitude_normalizes_the_same_way() -> None:
    line = "20151231, 0000,  , TS, 12.5S, 200.0E,  45, 1000" + ", 0" * 13
    (longitude,) = parse(f"EP991949,              TEST,      1,\n{line}")["longitude"]
    assert longitude == -160.0


@pytest.mark.parametrize("text", ["180.0W", "180.0E", "360.0W", "  0.0E"])
def test_longitudes_on_the_antimeridian_and_prime_meridian_stay_in_range(text: str) -> None:
    line = f"20151231, 0000,  , TS, 12.5S, {text},  45, 1000" + ", 0" * 13
    (longitude,) = parse(f"EP991949,              TEST,      1,\n{line}")["longitude"]
    assert -180.0 <= longitude <= 180.0


def test_files_without_a_terminating_newline_and_with_blank_lines_parse() -> None:
    body = MODERN.split("\n", 1)[1]
    assert parse(f"AL092021, IDA, 2,\n{body}") == parse(f"\nAL092021, IDA, 2,\n{body}\n")


def test_an_empty_file_yields_no_track_points() -> None:
    assert parse("") == {name: [] for name in COLUMNS}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("20210829, 1655, L, HU, 29.1N,  90.2W, 130,  931" + ", 0" * 13, "storm header"),
        ("AL092021, IDA, two,\n", "not a nonnegative integer"),
        ("AL092021, IDA, 2, extra,\n", "storm header"),
        ("al092021, IDA, 1,\n", "storm header"),
        ("AL092021, IDA, 3,\n" + MODERN.split("\n", 1)[1], "only 2 lines follow"),
        ("AL092021, IDA, 1,\n20210829, 1655, L, HU, 29.1N, 90.2W, 130,", "track fields"),
        (
            "AL092021, IDA, 1,\n20210829, 9999, L, HU, 29.1N,  90.2W, 130,  931" + ", 0" * 13,
            "UTC date and time",
        ),
        (
            "AL092021, IDA, 1,\n20210829, 1655, L, HU, 29.1X,  90.2W, 130,  931" + ", 0" * 13,
            "expected a latitude",
        ),
        (
            "AL092021, IDA, 1,\n20210829, 1655, L, HU, 29.1N, 360.2W, 130,  931" + ", 0" * 13,
            "expected a longitude",
        ),
        (
            "AL092021, IDA, 1,\n2021829, 1655, L, HU, 29.1N,  90.2W, 130,  931" + ", 0" * 13,
            "UTC date and time",
        ),
        (
            "AL092021, IDA, 1,\n20210829, 165, L, HU, 29.1N,  90.2W, 130,  931" + ", 0" * 13,
            "UTC date and time",
        ),
        (
            "AL092021, IDA, 1,\n20210829, 1655, L, HU, 29.1N,  90.2W, 13O,  931" + ", 0" * 13,
            "integer measurement",
        ),
        (
            "AL092021, IDA, 1,\n20210829, 1655, L, HU, north,  90.2W, 130,  931" + ", 0" * 13,
            "expected a latitude",
        ),
    ],
)
def test_malformed_layouts_name_the_offending_line(text: str, message: str) -> None:
    with pytest.raises(Hurdat2FormatError, match=message):
        parse(text)
