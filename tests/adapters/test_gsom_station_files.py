from pathlib import Path

import httpx
import pytest
import respx

from usdata.providers.base import QueryError
from usdata.providers.noaa.gsom_files import ACCESS_URL, GsomStationFiles
from usdata.query import build_query
from usdata.registry import default_registry

CSV = b'"STATION","DATE","SNOW","SNOW_ATTRIBUTES"\n"USW00094823","1997-12","320",",,,0"\n'


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield GsomStationFiles(default_registry().get("noaa:gsom-station-files"), client=client)


def test_each_station_is_one_whole_file_listed_without_a_request(adapter) -> None:
    with respx.mock() as mock:
        assets = adapter.list_assets(build_query(stations="usw00094823, USC00100667,USW00094823"))
        assert not mock.calls
    assert [asset.id for asset in assets] == ["USW00094823.csv", "USC00100667.csv"]
    first = assets[0]
    assert first.href == f"{ACCESS_URL}USW00094823.csv"
    assert first.media_type == "text/csv" and first.size is None
    assert first.time is not None and first.time.start.year == 1763 and first.time.end is None
    assert first.properties == {"units": "metric"}


@pytest.mark.parametrize(
    ("kwargs", "problem"),
    [
        ({}, "stations"),
        ({"stations": "USW0009482"}, "11-character"),
        ({"stations": "USW00094823", "start": "1997-11-01", "end": "1998-03-31"}, "start/end"),
        ({"stations": "USW00094823", "bbox": (-81, 40, -79, 41)}, "bbox"),
        ({"stations": "USW00094823", "variables": ["SNOW"]}, "variables"),
        ({"stations": "USW00094823", "units": "standard"}, "units"),
    ],
)
def test_what_a_station_file_cannot_select_is_refused(adapter, kwargs, problem) -> None:
    with respx.mock() as mock, pytest.raises(QueryError, match=problem):
        adapter.list_assets(build_query(**kwargs))
    assert not mock.calls


@pytest.mark.l2
def test_fetch_writes_the_station_file_as_served(adapter, tmp_path: Path) -> None:
    (asset,) = adapter.list_assets(build_query(stations="USW00094823"))
    with respx.mock() as mock:
        mock.get(asset.href).respond(200, content=CSV)
        written = adapter.fetch(asset, tmp_path / asset.id)
    assert written.read_bytes() == CSV


@pytest.mark.l2
def test_a_station_without_a_file_fails_at_fetch(adapter, tmp_path: Path) -> None:
    (asset,) = adapter.list_assets(build_query(stations="USC99999999"))
    with respx.mock() as mock:
        mock.get(asset.href).respond(404)
        with pytest.raises(httpx.HTTPStatusError):
            adapter.fetch(asset, tmp_path / asset.id)
    assert not (tmp_path / asset.id).exists()
