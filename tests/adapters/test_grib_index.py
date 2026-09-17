"""The wgrib2 index parser and message selection: pure, with no transport at all."""

from __future__ import annotations

import pytest

from usdata.providers.base import QueryError
from usdata.providers.noaa.grib_index import parse_index, parse_selector, resolve

URL = "s3://noaa-hrrr-bdp-pds/hrrr.20240506/conus/hrrr.t20z.wrfsfcf01.grib2"
SIZE = 5_000
INDEX = (
    "1:0:d=2024050620:REFC:entire atmosphere:1 hour fcst:\n"
    "2:1000:d=2024050620:TMP:2 m above ground:1 hour fcst:\n"
    "3:2500:d=2024050620:TMP:surface:1 hour fcst:\n"
    "4:4000:d=2024050620:HLCY:3000-0 m above ground:1 hour fcst:\n"
)


def entries(text: str = INDEX, size: int = SIZE):
    return parse_index(text, object_size=size, url=URL)


def selectors(*raw: str):
    return [parse_selector(item) for item in raw]


def test_lengths_come_from_the_next_offset_and_the_last_runs_to_the_object_end() -> None:
    parsed = entries()
    assert [e.number for e in parsed] == [1, 2, 3, 4]
    assert [e.offset for e in parsed] == [0, 1000, 2500, 4000]
    assert [e.length for e in parsed] == [1000, 1500, 1500, 1000]
    assert [(e.byte_range.start, e.byte_range.end) for e in parsed] == [
        (0, 999),
        (1000, 2499),
        (2500, 3999),
        (4000, 4999),
    ]
    assert parsed[1].byte_range.length == 1500
    assert parsed[1].label == "TMP:2 m above ground:1 hour fcst"


def test_blank_lines_and_trailing_fields_are_tolerated() -> None:
    text = (
        "\n"
        "1:0:d=2024050620:APCP:surface:0-1 hour acc fcst:\n"
        "\n"
        "2:2000:d=2024050620:APCP:surface:0-1 hour acc fcst:prob >0.254:\n"
    )
    parsed = parse_index(text, object_size=4000, url=URL)
    assert [(e.number, e.length, e.step) for e in parsed] == [
        (1, 2000, "0-1 hour acc fcst"),
        (2, 2000, "0-1 hour acc fcst"),
    ]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "lists no GRIB2 messages"),
        ("   \n\n", "lists no GRIB2 messages"),
        ("not an index at all\n", "is not a wgrib2 index line"),
        ("1:x:d=2024050620:TMP:surface:anl:\n", "has no message number and offset"),
        ("a:0:d=2024050620:TMP:surface:anl:\n", "has no message number and offset"),
        ("1:0:d=x:TMP:surface:anl:\n2:0:d=x:CAPE:surface:anl:\n", "share offset 0"),
        ("1:900:d=x:TMP:surface:anl:\n2:400:d=x:CAPE:surface:anl:\n", "is not inside the"),
        ("1:9000:d=x:TMP:surface:anl:\n", "is not inside the"),
    ],
)
def test_an_unparsable_index_names_the_object(text: str, message: str) -> None:
    with pytest.raises(QueryError, match=message) as error:
        parse_index(text, object_size=1000, url=URL)
    assert URL in str(error.value)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("TMP:2 m above ground", ("TMP", "2 m above ground", None)),
        (" TMP : surface ", ("TMP", "surface", None)),
        ("TMP:surface:1 hour fcst", ("TMP", "surface", "1 hour fcst")),
    ],
)
def test_selectors_take_a_short_name_a_level_and_an_optional_step(raw, expected) -> None:
    selector = parse_selector(raw)
    assert (selector.short_name, selector.level, selector.step) == expected
    assert selector.text == ":".join(part for part in expected if part)


@pytest.mark.parametrize("raw", ["TMP", "", ":", "TMP:", ":surface", "TMP:surface:anl:x:y"])
def test_a_malformed_selector_is_refused_with_the_spelling(raw: str) -> None:
    with pytest.raises(QueryError, match="must be 'VAR:level text'"):
        parse_selector(raw)


def test_selection_is_ascending_distinct_and_keeps_every_matching_message() -> None:
    chosen = resolve(
        entries(),
        selectors("HLCY:3000-0 m above ground", "TMP:2 m above ground", "TMP:2 m above ground"),
        url=URL,
    )
    assert [s.entry.number for s in chosen] == [2, 4]
    both_levels = resolve(entries(), selectors("TMP:surface", "TMP:2 m above ground"), url=URL)
    assert [s.entry.number for s in both_levels] == [2, 3]


def test_a_step_narrows_a_selector_that_would_otherwise_match_two_messages() -> None:
    text = (
        "1:0:d=x:TMP:surface:1 hour fcst:\n"
        "2:100:d=x:TMP:surface:2 hour fcst:\n"
        "3:200:d=x:CAPE:surface:1 hour fcst:\n"
    )
    parsed = parse_index(text, object_size=300, url=URL)
    assert [s.entry.number for s in resolve(parsed, selectors("TMP:surface"), url=URL)] == [1, 2]
    stepped = resolve(parsed, selectors("TMP:surface:2 hour fcst"), url=URL)
    assert [s.entry.number for s in stepped] == [2]


def test_each_selection_carries_text_naming_its_one_message() -> None:
    """A selector that named one message is kept; a broader one gives way to the index line."""
    text = (
        "1:0:d=x:TMP:surface:1 hour fcst:\n"
        "2:100:d=x:TMP:surface:2 hour fcst:\n"
        "3:200:d=x:CAPE:surface:1 hour fcst:\n"
    )
    parsed = parse_index(text, object_size=300, url=URL)
    exact = resolve(parsed, selectors("CAPE:surface"), url=URL)
    assert [s.selector for s in exact] == ["CAPE:surface"]
    broad = resolve(parsed, selectors("TMP:surface"), url=URL)
    assert [s.selector for s in broad] == ["TMP:surface:1 hour fcst", "TMP:surface:2 hour fcst"]


def test_an_unknown_level_lists_the_levels_that_short_name_publishes() -> None:
    with pytest.raises(QueryError, match="matched no message") as error:
        resolve(entries(), selectors("TMP:800 mb"), url=URL)
    assert "'TMP:800 mb'" in str(error.value)
    assert "levels published for TMP: 2 m above ground, surface" in str(error.value)


def test_an_unknown_short_name_lists_the_nearest_ones() -> None:
    with pytest.raises(QueryError, match="nearest short names") as error:
        resolve(entries(), selectors("TMPK:surface"), url=URL)
    assert "'TMPK:surface'" in str(error.value)
    assert "TMP" in str(error.value)
    assert URL in str(error.value)


def test_a_selector_matching_nothing_never_yields_the_whole_file() -> None:
    with pytest.raises(QueryError):
        resolve(entries(), selectors("TMP:2 m above ground", "PRES:nope"), url=URL)


def test_fields_of_one_message_share_a_range_and_select_it_once() -> None:
    """RAP packs wind components as fields 12.1 and 12.2 of one message at one offset."""
    text = (
        "11:0:d=x:VVEL:100 mb:anl:\n"
        "12.1:100:d=x:UGRD:100 mb:anl:\n"
        "12.2:100:d=x:VGRD:100 mb:anl:\n"
        "13:250:d=x:HGT:125 mb:anl:\n"
    )
    parsed = parse_index(text, object_size=300, url=URL)
    assert [(e.number, e.field, e.offset, e.length) for e in parsed] == [
        (11, None, 0, 100),
        (12, 1, 100, 150),
        (12, 2, 100, 150),
        (13, None, 250, 50),
    ]
    one = resolve(parsed, selectors("VGRD:100 mb"), url=URL)
    assert [(s.entry.number, s.selector) for s in one] == [(12, "VGRD:100 mb")]
    both = resolve(parsed, selectors("UGRD:100 mb", "VGRD:100 mb"), url=URL)
    assert [(s.entry.number, s.entry.byte_range.start, s.selector) for s in both] == [
        (12, 100, "UGRD:100 mb")
    ]


def test_a_further_index_text_is_named_to_be_selected_and_excluded_otherwise() -> None:
    """NBM lines carry a fourth text for ensemble spread and probability thresholds."""
    text = (
        "1:0:d=x:TMP:2 m above ground:1 hour fcst:\n"
        "2:100:d=x:TMP:2 m above ground:1 hour fcst:ens std dev\n"
        "3:200:d=x:APCP:surface:0-1 hour acc fcst:prob >0.254:prob fcst 255/255\n"
        "4:300:d=x:APCP:surface:0-1 hour acc fcst:\n"
    )
    parsed = parse_index(text, object_size=400, url=URL)
    assert [e.extra for e in parsed] == ["", "ens std dev", "prob >0.254:prob fcst 255/255", ""]
    plain = resolve(parsed, selectors("TMP:2 m above ground"), url=URL)
    assert [s.entry.number for s in plain] == [1]
    spread = resolve(parsed, selectors("TMP:2 m above ground:1 hour fcst:ens std dev"), url=URL)
    assert [(s.entry.number, s.selector) for s in spread] == [
        (2, "TMP:2 m above ground:1 hour fcst:ens std dev")
    ]
    assert [s.entry.number for s in resolve(parsed, selectors("APCP:surface"), url=URL)] == [4]
    assert parsed[2].label == "APCP:surface:0-1 hour acc fcst:prob >0.254:prob fcst 255/255"
    selector = parse_selector("TMP:2 m above ground:1 hour fcst:ens std dev")
    assert (selector.step, selector.extra) == ("1 hour fcst", "ens std dev")
