from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

from usdata.providers.base import QueryError
from usdata.providers.noaa.enso import INDEX_URL, EnsoIndices
from usdata.query import build_query
from usdata.registry import default_registry

RONI = b"SEAS   YR  ANOM\nDJF  1950 -1.19\nJFM  1950 -1.08\n"


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield EnsoIndices(default_registry().get("noaa:enso-indices"), client=client)


@pytest.mark.parametrize(
    ("params", "name"),
    [
        ({}, "RONI.ascii.txt"),
        ({"index": "roni"}, "RONI.ascii.txt"),
        ({"index": "oni"}, "oni.ascii.txt"),
    ],
)
def test_one_whole_table_is_listed_without_a_request(adapter, params, name) -> None:
    with respx.mock() as mock:
        (asset,) = adapter.list_assets(build_query(**params))
        assert not mock.calls
    assert asset.id == name and asset.href == INDEX_URL + name
    assert asset.media_type == "text/plain" and asset.size is None
    assert asset.time is not None
    assert asset.time.start == datetime(1949, 12, 1, tzinfo=UTC) and asset.time.end is None


@pytest.mark.parametrize(
    ("kwargs", "problem"),
    [
        ({"start": "2026-06-01", "end": "2026-08-31"}, "start/end"),
        ({"bbox": (-170, -5, -120, 5)}, "bbox"),
        ({"variables": ["ANOM"]}, "variables"),
        ({"index": "nino34"}, "index"),
        ({"version": "v5"}, "version"),
    ],
)
def test_what_a_table_cannot_select_is_refused(adapter, kwargs, problem) -> None:
    with respx.mock() as mock, pytest.raises(QueryError, match=problem):
        adapter.list_assets(build_query(**kwargs))
    assert not mock.calls


@pytest.mark.l2
def test_fetch_writes_the_table_as_served(adapter, tmp_path: Path) -> None:
    (asset,) = adapter.list_assets(build_query())
    with respx.mock() as mock:
        mock.get(asset.href).respond(200, content=RONI)
        written = adapter.fetch(asset, tmp_path / asset.id)
    assert written.read_bytes() == RONI
