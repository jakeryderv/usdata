"""IEM watch/warning archive: the place and filter parameters, monthly assets, and the zip path."""

import io
import zipfile
from pathlib import Path

import httpx
import pytest
import respx

from usdata import build_query, get
from usdata.models import Query
from usdata.providers.base import QueryError
from usdata.providers.noaa.nws_warnings import SERVICE_URL, NwsWarnings, NwsWarningsParams

EVENING = {"start": "2024-05-06T18:00Z", "end": "2024-05-07T12:00Z"}


def service_zip(built: tuple[int, int, int, int, int, int]) -> bytes:
    """A zip as the service sends it, stamped with when it was built, the DBF header too."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        header = b"\x03" + bytes([built[0] - 1900, built[1], built[2]])
        for name, data in (
            ("wwa.shp", b"shapes"),
            ("wwa.dbf", header + b"rows"),
            ("wwa.csv", b"WFO\n"),
        ):
            archive.writestr(zipfile.ZipInfo(name, date_time=built), data)
    return buffer.getvalue()


def adapter() -> NwsWarnings:
    return NwsWarnings(get("noaa:nws-warnings"))


def query(**kwargs):
    return build_query(**{**EVENING, **kwargs})


def listed(**kwargs) -> list[httpx.URL]:
    """The URLs a query's assets name; listing itself makes no request."""
    with adapter() as provider, respx.mock() as mock:
        assets = provider.list_assets(query(**kwargs))
        assert not mock.calls
    return [httpx.URL(asset.href) for asset in assets]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start": None, "end": None},
        {"end": None},
        {"text": "tornado"},
        {"variables": ["PHENOM"]},
        {"bbox": (-97.1, 36.1, -96.0, 37.0)},
        {"lat": 36.6, "lon": -96.4},
        {"location": "Osage County, OK"},
        {"location": "Oklahoma", "wfo": "OUN"},
        {"events": "TOW"},
        {"events": "TO.WW"},
        {"events": ""},
        {"wfo": "OU"},
        {"wfo": "OUN1"},
        {"storm_based": "yes"},
        {"followups": 1},
        {"typo": 1},
    ],
)
def test_bad_queries_fail_before_network(kwargs) -> None:
    with adapter() as provider, pytest.raises(QueryError), respx.mock() as mock:
        provider.list_assets(query(**kwargs))
    assert not mock.calls


def message(**params: object) -> str:
    with adapter() as provider, pytest.raises(QueryError) as raised:
        provider.parse_params(Query(params=params), NwsWarningsParams)
    return str(raised.value)


def test_refusals_say_what_to_do_instead() -> None:
    assert "such as TO.W" in message(events="TOW")
    assert "three or four letters" in message(wfo="O1N")
    cases = {
        "does not support bbox or lat/lon": {"lat": 36.6, "lon": -96.4},
        "Osage County, OK is a county; name its state": {"location": "Osage County, OK"},
        "noaa:nws-vtec-events": {"location": "Osage County, OK"},
        "a location and wfo; pass one of them": {"location": "Oklahoma", "wfo": "OUN"},
        "the shapefile's columns are fixed": {"variables": ["PHENOM"]},
    }
    for expected, kwargs in cases.items():
        with adapter() as provider, pytest.raises(QueryError, match=expected):
            provider.list_assets(query(**kwargs))


def test_the_whole_archive_is_asked_for_unless_narrowed() -> None:
    (url,) = listed()
    assert url.params["accept"] == "shapefile"
    narrowing = {"location_group", "states", "wfo", "phenomena", "limitps", "limit1", "addsvs"}
    assert not narrowing & set(url.params)


def test_a_state_or_offices_narrow_the_rows() -> None:
    (state,) = listed(location="Oklahoma")
    assert (state.params["location_group"], state.params["states"]) == ("states", "OK")
    (offices,) = listed(wfo="oun,TSA")
    assert (offices.params["location_group"], offices.params["wfo"]) == ("wfo", "OUN,TSA")


def test_events_are_sent_as_aligned_phenomena_and_significance() -> None:
    (url,) = listed(events="to.w,SV.W,TO.A")
    assert url.params["limitps"] == "1"
    assert url.params["phenomena"] == "TO,SV,TO"
    assert url.params["significance"] == "W,W,A"


def test_polygon_options_map_to_the_service_flags() -> None:
    (url,) = listed(storm_based=True, followups="true")
    assert (url.params["limit1"], url.params["addsvs"]) == ("1", "1")


def test_the_window_is_sent_with_an_exclusive_end_one_second_later() -> None:
    (url,) = listed()
    assert url.params["sts"] == "2024-05-06T18:00:00Z"
    assert url.params["ets"] == "2024-05-07T12:00:01Z"
    (offset,) = listed(start="2024-05-06T13:00-05:00", end="2024-05-07T07:00-05:00")
    assert (offset.params["sts"], offset.params["ets"]) == (url.params["sts"], url.params["ets"])


def test_a_window_becomes_one_zip_per_utc_month() -> None:
    urls = listed(start="2024-04-30T12:00Z", end="2024-06-01T00:00Z")
    assert [(url.params["sts"], url.params["ets"]) for url in urls] == [
        ("2024-04-30T12:00:00Z", "2024-05-01T00:00:00Z"),
        ("2024-05-01T00:00:00Z", "2024-06-01T00:00:00Z"),
        ("2024-06-01T00:00:00Z", "2024-06-01T00:00:01Z"),
    ]


def test_assets_have_stable_ids_naming_their_span() -> None:
    with adapter() as provider:
        first = provider.list_assets(query())
        again = provider.list_assets(query())
        narrowed = provider.list_assets(query(events="TO.W"))
        months = provider.list_assets(query(start="2024-04-30T12:00Z", end="2024-05-07"))
    assert first == again and len(first) == 1
    (asset,) = first
    assert asset.id.startswith("wwa_20240506_20240507_") and asset.id.endswith(".zip")
    assert asset.media_type == "application/zip" and asset.size is None
    assert asset.time is not None and asset.time.end is not None
    assert asset.time.end.isoformat() == "2024-05-07T12:00:00+00:00"
    assert asset.id != narrowed[0].id
    assert [a.id[:21] for a in months] == ["wwa_20240430_20240430", "wwa_20240501_20240507"]


@pytest.mark.l2
def test_fetch_writes_the_canonical_zip(tmp_path: Path) -> None:
    from usdata import fetch

    with respx.mock() as mock:
        route = mock.get(url__startswith=SERVICE_URL).respond(
            200, content=service_zip((2026, 10, 8, 18, 35, 38))
        )
        (item,) = fetch(get("noaa:nws-warnings"), query(), root=tmp_path)
    assert route.call_count == 1
    with zipfile.ZipFile(item.path) as archive:
        assert archive.namelist() == ["wwa.shp", "wwa.dbf", "wwa.csv"]
        assert {info.date_time for info in archive.infolist()} == {(1980, 1, 1, 0, 0, 0)}
    assert item.provenance.transformations[0].startswith("iem canonical zip")
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.l2
def test_a_zip_built_on_another_day_restores_to_the_same_checksum(tmp_path: Path) -> None:
    from usdata import fetch

    checksums = []
    for day, root in ((8, tmp_path / "a"), (9, tmp_path / "b")):
        with respx.mock() as mock:
            mock.get(url__startswith=SERVICE_URL).respond(
                200, content=service_zip((2026, 10, day, 3, 0, 0))
            )
            (item,) = fetch(get("noaa:nws-warnings"), query(), root=root)
        checksums.append(item.provenance.checksum)
    assert checksums[0] == checksums[1]


@pytest.mark.l2
def test_an_answer_that_is_not_a_zip_is_an_error_naming_it(tmp_path: Path) -> None:
    from usdata import fetch

    with respx.mock() as mock:
        mock.get(url__startswith=SERVICE_URL).respond(200, content=b"Requests are limited.\n")
        with pytest.raises(httpx.DecodingError, match="Requests are limited"):
            fetch(get("noaa:nws-warnings"), query(), root=tmp_path)
    assert not [path for path in tmp_path.rglob("*") if path.is_file()]
