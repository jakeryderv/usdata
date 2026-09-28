from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

from usdata.providers.base import QueryError
from usdata.providers.noaa.ersst import DIRECTORY_URL, Ersst, month_starts
from usdata.query import build_query
from usdata.registry import default_registry

DATA = b"\x89HDF\r\n\x1a\nmock ERSST month"


def listing(*months: str, size: int = 168286) -> str:
    """The directory index NCEI serves, one row per monthly file."""
    rows = "".join(
        f'<tr><td><a href="ersst.v6.{month}.nc">ersst.v6.{month}.nc</a></td>'
        f'<td align="right">2026-09-03 14:28</td><td align="right">{size}</td><td> </td></tr>'
        for month in months
    )
    return (
        '<table><tr><th><a href="?C=N;O=D">Name</a></th></tr>'
        '<tr><td><a href="/data/sea-surface-temperature-extended-reconstructed/v6/">'
        "Parent Directory</a></td></tr>"
        f'{rows}<tr><td><a href="Readme.Status.Changes.ann">Readme</a></td></tr></table>'
    )


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield Ersst(default_registry().get("noaa:ersst"), client=client)


def test_every_month_the_window_touches_is_one_whole_file(adapter) -> None:
    with respx.mock() as mock:
        route = mock.get(DIRECTORY_URL).respond(200, text=listing("202605", "202606", "202607"))
        assets = adapter.list_assets(build_query(start="2026-06-15", end="2026-07-01"))
    assert route.call_count == 1
    assert [asset.id for asset in assets] == ["ersst.v6.202606.nc", "ersst.v6.202607.nc"]
    june = assets[0]
    assert june.href == f"{DIRECTORY_URL}ersst.v6.202606.nc"
    assert june.size == 168286 and june.media_type == "application/x-netcdf"
    assert june.time is not None
    assert june.time.start == datetime(2026, 6, 1, tzinfo=UTC)
    assert june.time.end == datetime(2026, 6, 30, 23, 59, 59, 999999, tzinfo=UTC)


def test_a_window_inside_one_month_selects_that_month(adapter) -> None:
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing("202402", "202403"))
        (asset,) = adapter.list_assets(build_query(start="2024-02-29", end="2024-02-29"))
    assert asset.id == "ersst.v6.202402.nc"
    assert asset.time is not None and asset.time.end.day == 29


def test_month_starts_cross_a_year() -> None:
    months = month_starts(datetime(1997, 11, 20, tzinfo=UTC), datetime(1998, 1, 1, tzinfo=UTC))
    assert [f"{month:%Y-%m}" for month in months] == ["1997-11", "1997-12", "1998-01"]


def test_an_unpublished_month_is_named_with_the_newest_one(adapter) -> None:
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing("202607", "202608"))
        with pytest.raises(QueryError) as error:
            adapter.list_assets(build_query(start="2026-08-01", end="2026-10-31"))
    assert "2026-09, 2026-10" in str(error.value)
    assert "newest published month is 2026-08" in str(error.value)


def test_a_listing_without_monthly_files_is_refused(adapter) -> None:
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing())
        with pytest.raises(QueryError, match="lists no ERSST v6 monthly files"):
            adapter.list_assets(build_query(start="2026-08-01", end="2026-08-31"))


@pytest.mark.parametrize(
    ("kwargs", "problem"),
    [
        ({"start": "1849-12-01", "end": "1850-01-31"}, "start in January 1850"),
        ({"start": "2026-08-01", "end": "2026-08-31", "bbox": (-170, -5, -120, 5)}, "bbox"),
        ({"start": "2026-08-01", "end": "2026-08-31", "variables": ["sst"]}, "variables"),
        ({"start": "2026-08-01", "end": "2026-08-31", "version": "v5"}, "version"),
        ({"start": "2026-08-01"}, "start and end"),
    ],
)
def test_bad_queries_fail_before_any_request(adapter, kwargs, problem) -> None:
    with respx.mock() as mock, pytest.raises(QueryError, match=problem):
        adapter.list_assets(build_query(**kwargs))
    assert not mock.calls


@pytest.mark.l2
def test_fetch_writes_the_published_bytes(adapter, tmp_path: Path) -> None:
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing("202608"))
        (asset,) = adapter.list_assets(build_query(start="2026-08-01", end="2026-08-31"))
        mock.get(asset.href).respond(200, content=DATA)
        written = adapter.fetch(asset, tmp_path / asset.id)
    assert written.read_bytes() == DATA
