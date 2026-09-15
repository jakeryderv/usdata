from __future__ import annotations

from datetime import UTC
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata import ChecksumMismatch, fetch, provenance
from usdata.cache import sha256_file
from usdata.cli import app
from usdata.models import Protocol
from usdata.providers.base import QueryError
from usdata.providers.noaa.spc import DATA_URL, PAGE_URL, SpcTornadoReports
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.l2

CSV = (
    b"om,yr,mo,dy,date,time,tz,st,stf,stn,mag,inj,fat,loss,closs,slat,slon,elat,elon,len,wid,"
    b"ns,sn,sg,f1,f2,f3,f4,fc\n"
    b"623402,2024,01,05,2024-01-05,05:56:00,3,TX,48,0,0,0,0,0,0,29.0583,-95.5023,29.0666,"
    b"-95.5002,0.5900,200,1,1,1,39,0,0,0,0\n"
    b"623403,2024,01,06,2024-01-06,14:32:00,3,FL,12,0,-9,0,0,0,0,26.5273,-80.4902,26.5274,"
    b"-80.4776,0.7800,100,1,1,1,99,0,0,0,0\n"
)
ALL_NAMES = (
    "50-59_torn.csv",
    "60-69_torn.csv",
    "70-79_torn.csv",
    "80-89_torn.csv",
    "90-99_torn.csv",
    "2000-2004_torn.csv",
    "2005-2007_torn.csv",
    "2008_torn.csv",
    "2023_torn.csv",
    "2024_torn.csv",
)
MANIFEST = """name: tornadoes
sources:
  - dataset: noaa:spc-tornado-reports
    start: 2024-04-01
    end: 2024-04-30
"""


def page(*hrefs: str) -> str:
    """The SPC page shape: links in table cells beside approximate sizes and update notes."""
    return (
        "<html><body><table>"
        + "".join(
            f'<tr><td><a href="{href}">{href} (0.2 mb)<br></a><b>Updated: 23 Apr 2026</b>'
            f'</td><td><a href="{href.replace("torn", "hail")}">hail</a></td></tr>'
            for href in hrefs
        )
        + "</table></body></html>"
    )


def links(*names: str) -> str:
    return page(*(f"data/{name}" for name in names))


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield SpcTornadoReports(default_registry().get("noaa:spc-tornado-reports"), client=client)


def test_selects_annual_and_multi_year_files_with_file_year_bounds(adapter) -> None:
    with respx.mock() as mock:
        route = mock.get(PAGE_URL).respond(200, text=links(*ALL_NAMES))
        assets = adapter.list_assets(build_query(start="1999-12-31", end="2000-01-01"))
        decade = adapter.list_assets(build_query(start="1955-06-01", end="1955-06-02"))
        span = adapter.list_assets(build_query(start="2005-06-01", end="2008-01-01"))
        assert route.call_count == 3
    assert [a.id for a in assets] == ["90-99_torn.csv", "2000-2004_torn.csv"]
    assert [a.id for a in decade] == ["50-59_torn.csv"]
    assert [a.id for a in span] == ["2005-2007_torn.csv", "2008_torn.csv"]
    assert all(a.size is None for a in assets)
    assert all(a.protocol == Protocol.HTTP and a.media_type == "text/csv" for a in assets)
    assert assets[0].href == DATA_URL + "90-99_torn.csv"
    assert assets[0].time.start.isoformat() == "1990-01-01T00:00:00+00:00"
    assert assets[0].time.end.isoformat() == "1999-12-31T23:59:59.999999+00:00"
    assert decade[0].time.start.year == 1950 and decade[0].time.end.year == 1959
    assert assets[1].time.end.tzinfo == UTC


def test_narrowest_covering_file_wins_and_wide_files_only_fill_gaps(adapter) -> None:
    with respx.mock() as mock:
        mock.get(PAGE_URL).respond(
            200, text=links("1950-2024_torn.csv", "2024_torn.csv", "2023_torn.csv")
        )
        recent = adapter.list_assets(build_query(start="2024-05-06", end="2024-05-07"))
        gap = adapter.list_assets(build_query(start="1960-01-01", end="1960-12-31"))
        both = adapter.list_assets(build_query(start="2022-01-01", end="2024-12-31"))
    assert [a.id for a in recent] == ["2024_torn.csv"]
    assert [a.id for a in gap] == ["1950-2024_torn.csv"]
    assert [a.id for a in both] == ["1950-2024_torn.csv", "2023_torn.csv", "2024_torn.csv"]


def test_calendar_year_normalization_and_duplicate_links(adapter) -> None:
    with respx.mock() as mock:
        mock.get(PAGE_URL).respond(200, text=links("2024_torn.csv", "2024_torn.csv"))
        a = adapter.list_assets(
            build_query(start="2025-01-01T00:30+02:00", end="2025-01-01T00:30+02:00")
        )
        b = adapter.list_assets(build_query(start="2024-01-01", end="2024-12-31"))
    assert a == b and len(a) == 1 and a[0].id == "2024_torn.csv"


def test_ignores_other_tables_archives_and_nonlocal_links(adapter) -> None:
    with respx.mock() as mock:
        mock.get(PAGE_URL).respond(
            200,
            text=page(
                "data/2024_torn.csv",
                "data/2024_hail.csv",
                "data/2024_wind.csv",
                "data/1950-2024_torn.csv.zip",
                "data/1950-2024_actual_tornadoes.csv",
                "data/1950-2024_all_tornadoes.csv",
                "https://example.test/data/2023_torn.csv",
                "../data/2023_torn.csv",
                "data/49-59_torn.csv",
                "data/2010-2009_torn.csv",
            ),
        )
        assets = adapter.list_assets(build_query(start="2024-01-01", end="2024-12-31"))
        with pytest.raises(QueryError, match="2023"):
            adapter.list_assets(build_query(start="2023-01-01", end="2023-12-31"))
        with pytest.raises(QueryError, match="1955"):
            adapter.list_assets(build_query(start="1955-01-01", end="1955-12-31"))
    assert [a.id for a in assets] == ["2024_torn.csv"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"start": "2024-01-01"},
        {"end": "2024-12-31"},
        {"start": "1949-12-31", "end": "1950-01-01"},
        {"location": "OK"},
        {"variables": ["mag"]},
        {"text": "tornado"},
        {"year": 2024},
        {"table": "hail"},
        {"segments": "actual"},
    ],
)
def test_rejects_unsupported_or_incomplete_queries_before_network(adapter, kwargs) -> None:
    if not (not kwargs or "start" in kwargs or "end" in kwargs):
        kwargs = {"start": "2024-01-01", "end": "2024-12-31", **kwargs}
    with respx.mock() as mock, pytest.raises(QueryError):
        adapter.list_assets(build_query(**kwargs))
    assert not mock.calls


@pytest.mark.parametrize(
    "body", [links("2024_torn.csv"), links("2023_hail.csv"), "<html>unavailable</html>"]
)
def test_missing_years_never_return_partial_selection(adapter, body) -> None:
    with respx.mock() as mock:
        mock.get(PAGE_URL).respond(200, text=body)
        with pytest.raises(QueryError, match="2025"):
            adapter.list_assets(build_query(start="2024-01-01", end="2025-12-31"))


def test_listing_http_errors_surface(adapter) -> None:
    with respx.mock() as mock:
        mock.get(PAGE_URL).respond(503)
        with pytest.raises(httpx.HTTPStatusError):
            adapter.list_assets(build_query(start="2024-01-01", end="2024-12-31"))


def test_fetch_preserves_bytes_and_reuses_the_cache(tmp_path: Path) -> None:
    dataset = default_registry().get("noaa:spc-tornado-reports")
    with respx.mock() as mock:
        mock.get(PAGE_URL).respond(200, text=links("2024_torn.csv"))
        data = mock.get(DATA_URL + "2024_torn.csv").respond(200, content=CSV)
        (first,) = fetch(dataset, build_query(start="2024-04-01", end="2024-04-30"), root=tmp_path)
        (cached,) = fetch(dataset, build_query(start="2024-11-01", end="2024-11-02"), root=tmp_path)
    assert first.path.read_bytes() == CSV and first.provenance.size == len(CSV)
    assert first.provenance.checksum == sha256_file(first.path)
    assert first.provenance.transformations == []
    assert cached.from_cache and data.call_count == 1


def test_locked_restore_bypasses_the_page_and_rejects_revised_bytes(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    url = DATA_URL + "2024_torn.csv"
    with respx.mock() as mock:
        mock.get(PAGE_URL).respond(200, text=links("2024_torn.csv"))
        mock.get(url).respond(200, content=CSV)
        initial = pull(manifest, root=tmp_path)
    path = initial.fetched[0].path
    path.unlink()
    with respx.mock(assert_all_called=False) as mock:
        listing_route = mock.get(PAGE_URL).respond(200, text=links("2024_torn.csv"))
        old = mock.get(url).respond(200, content=CSV)
        restored = pull(manifest, root=tmp_path)
    assert old.called and not listing_route.called
    assert restored.fetched[0].asset.id == "2024_torn.csv" and verify(manifest, root=tmp_path) == []
    path.unlink()
    with respx.mock() as mock:
        mock.get(url).respond(200, content=CSV + b"623404,2024,01,07,x\n")
        with pytest.raises(ChecksumMismatch):
            pull(manifest, root=tmp_path)
    assert not path.exists()


def test_csv_reader_is_local_and_accepts_fips_string_overrides(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    dataset = default_registry().get("noaa:spc-tornado-reports")
    with respx.mock() as mock:
        mock.get(PAGE_URL).respond(200, text=links("2024_torn.csv"))
        mock.get(DATA_URL + "2024_torn.csv").respond(200, content=CSV)
        (fetched,) = fetch(
            dataset, build_query(start="2024-01-01", end="2024-12-31"), root=tmp_path
        )
    before = fetched.path.read_bytes(), provenance.read(fetched.path)
    with respx.mock() as mock:
        frame = fetched.open(dtype={"stf": "string", "f1": "string"}, parse_dates=["date"])
        assert not mock.calls
    assert list(frame["om"]) == [623402, 623403] and list(frame["mag"]) == [0, -9]
    assert list(frame["stf"]) == ["48", "12"] and str(frame["stf"].dtype).startswith("string")
    assert frame["date"].dt.year.tolist() == [2024, 2024]
    assert frame.attrs["usdata"]["provenance"]["checksum"] == before[1].checksum
    assert (fetched.path.read_bytes(), provenance.read(fetched.path)) == before


def test_cli_dry_run_and_rejected_geographic_filter() -> None:
    runner = CliRunner()
    args = ["fetch", "noaa:spc-tornado-reports", "--start", "2024-04-01", "--end", "2024-04-30"]
    with respx.mock() as mock:
        mock.get(PAGE_URL).respond(200, text=links("2024_torn.csv"))
        result = runner.invoke(app, [*args, "--dry-run"])
    assert result.exit_code == 0
    assert result.stdout == f"2024_torn.csv\t{DATA_URL}2024_torn.csv\n"
    with respx.mock() as mock:
        bad = runner.invoke(app, [*args, "--location", "OK"])
    assert bad.exit_code == 2 and "filter locally" in bad.output and not mock.calls
