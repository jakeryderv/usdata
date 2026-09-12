from __future__ import annotations

import gzip
from datetime import UTC
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata import provenance
from usdata.cache import sha256_file
from usdata.cli import app
from usdata.fetch import ChecksumMismatch, fetch
from usdata.models import Protocol
from usdata.providers.base import QueryError
from usdata.providers.noaa.storm_events import DIRECTORY_URL, StormEvents
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.readers import UnsupportedFormat
from usdata.registry import default_registry

pytestmark = pytest.mark.l2

FIXTURE = Path(__file__).parents[1] / "fixtures" / "storm-details-1950.csv"
CSV = FIXTURE.read_bytes()
GZIP = gzip.compress(CSV, mtime=0)
NAME = "StormEvents_details-ftp_v1.0_d1950_c20260323.csv.gz"
URL = DIRECTORY_URL + NAME
MANIFEST = """name: storms
sources:
  - dataset: noaa:storm-events
    start: 1950-04-01
    end: 1950-04-30
"""


def listing(*entries: tuple[str, str]) -> str:
    return (
        "<table>"
        + "".join(
            f'<tr><td><a href="{name}">{name}</a></td><td>2026-03-23 13:10</td>'
            f'<td align="right">{size}</td><td></td></tr>'
            for name, size in entries
        )
        + "</table>"
    )


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield StormEvents(default_registry().get("noaa:storm-events"), client=client)


def test_selects_latest_revision_and_preserves_exact_sizes_and_year_bounds(adapter) -> None:
    older = NAME.replace("20260323", "20250301")
    next_year = NAME.replace("d1950", "d1951")
    invalid_date = NAME.replace("20260323", "20261301")
    with respx.mock() as mock:
        route = mock.get(DIRECTORY_URL).respond(
            200,
            text=listing(
                (NAME, "10.3K"),
                (older, "9999"),
                (next_year, "11920"),
                (invalid_date, "4"),
                ("../" + NAME, "1"),
                ("https://example.test/" + NAME, "2"),
                (NAME.replace("details", "fatalities"), "3"),
                (NAME.replace("v1.0", "v2.0"), "5"),
            ),
        )
        assets = adapter.list_assets(build_query(start="1950-12-31", end="1951-01-01"))
        assert route.call_count == 1
    assert [a.id for a in assets] == [NAME, next_year]
    assert [a.size for a in assets] == [None, 11920]
    assert all(a.protocol == Protocol.HTTP and a.media_type == "application/gzip" for a in assets)
    assert assets[0].href == URL
    assert assets[0].time.start.isoformat() == "1950-01-01T00:00:00+00:00"
    assert assets[0].time.end.isoformat() == "1950-12-31T23:59:59.999999+00:00"
    assert assets[1].time.end.tzinfo == UTC


def test_calendar_year_normalization_and_duplicate_rows(adapter) -> None:
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing((NAME, "10508"), (NAME, "10508")))
        a = adapter.list_assets(
            build_query(start="1951-01-01T00:30+02:00", end="1951-01-01T00:30+02:00")
        )
        b = adapter.list_assets(build_query(start="1950-01-01", end="1950-12-31"))
    assert a == b and len(a) == 1 and a[0].size == 10508


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"start": "1950-01-01"},
        {"end": "1950-12-31"},
        {"start": "1949-12-31", "end": "1950-01-01"},
        {"location": "OK"},
        {"variables": ["EVENT_TYPE"]},
        {"text": "tornado"},
        {"year": 1950},
        {"table": "fatalities"},
        {"event_type": "Tornado"},
        {"revision": "20260323"},
    ],
)
def test_rejects_unsupported_or_incomplete_queries_before_network(adapter, kwargs) -> None:
    if not (not kwargs or "start" in kwargs or "end" in kwargs):
        kwargs = {"start": "1950-01-01", "end": "1950-12-31", **kwargs}
    with respx.mock() as mock, pytest.raises(QueryError):
        adapter.list_assets(build_query(**kwargs))
    assert not mock.calls


@pytest.mark.parametrize(
    "body",
    [
        listing((NAME, "10508")),
        listing((NAME.replace("v1.0", "v2.0"), "1")),
        "<html>unavailable</html>",
    ],
)
def test_missing_years_never_return_partial_archive_selection(adapter, body) -> None:
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=body)
        with pytest.raises(QueryError, match="1951"):
            adapter.list_assets(build_query(start="1950-01-01", end="1951-12-31"))


def test_listing_http_errors_surface(adapter) -> None:
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(404)
        with pytest.raises(httpx.HTTPStatusError):
            adapter.list_assets(build_query(start="1950-01-01", end="1950-12-31"))


@pytest.mark.l2
def test_fetch_preserves_gzip_bytes_and_cache_provenance(tmp_path: Path) -> None:
    dataset = default_registry().get("noaa:storm-events")
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing((NAME, str(len(GZIP)))))
        data = mock.get(URL).respond(200, content=GZIP)
        (first,) = fetch(dataset, build_query(start="1950-04-01", end="1950-04-30"), root=tmp_path)
        (cached,) = fetch(dataset, build_query(start="1950-04-28", end="1950-04-28"), root=tmp_path)
    assert first.path.read_bytes() == GZIP and first.provenance.size == len(GZIP)
    assert gzip.decompress(first.path.read_bytes()) == CSV
    assert first.provenance.checksum == sha256_file(first.path)
    assert first.provenance.transformations == []
    assert cached.from_cache and data.call_count == 1


@pytest.mark.l2
def test_locked_restore_pins_revision_and_rejects_changed_bytes(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    newer = NAME.replace("20260323", "20260901")
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing((NAME, str(len(GZIP)))))
        mock.get(URL).respond(200, content=GZIP)
        initial = pull(manifest, root=tmp_path)
    path = initial.fetched[0].path
    path.unlink()
    with respx.mock(assert_all_called=False) as mock:
        listing_route = mock.get(DIRECTORY_URL).respond(200, text=listing((newer, str(len(GZIP)))))
        old = mock.get(URL).respond(200, content=GZIP)
        restored = pull(manifest, root=tmp_path)
    assert old.called and not listing_route.called
    assert restored.fetched[0].asset.id == NAME and verify(manifest, root=tmp_path) == []
    path.unlink()
    with respx.mock() as mock:
        mock.get(URL).respond(200, content=gzip.compress(CSV + b"\n", mtime=0))
        with pytest.raises(ChecksumMismatch):
            pull(manifest, root=tmp_path)
    assert not path.exists()
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(
            200, text=listing((NAME, str(len(GZIP))), (newer, str(len(GZIP))))
        )
        mock.get(DIRECTORY_URL + newer).respond(200, content=GZIP)
        updated = pull(manifest, root=tmp_path, force=True)
    assert updated.fetched[0].asset.id == newer
    assert updated.fetched[0].path != path


@pytest.mark.l2
def test_gzip_csv_reader_is_local_preserves_ids_options_and_source(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    dataset = default_registry().get("noaa:storm-events")
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing((NAME, str(len(GZIP)))))
        mock.get(URL).respond(200, content=GZIP)
        (fetched,) = fetch(
            dataset, build_query(start="1950-01-01", end="1950-12-31"), root=tmp_path
        )
    before = fetched.path.read_bytes(), provenance.read(fetched.path)
    with respx.mock() as mock:
        frame = fetched.open(usecols=["EVENT_ID", "STATE_FIPS", "CZ_FIPS", "EVENT_TYPE"], nrows=2)
        assert not mock.calls
    assert list(frame.EVENT_ID) == ["10096222", "10120412"]
    assert str(frame.STATE_FIPS.dtype).startswith("string")
    assert str(frame.CZ_FIPS.dtype).startswith("string")
    assert frame.attrs["usdata"]["provenance"]["checksum"] == before[1].checksum
    assert (fetched.path.read_bytes(), provenance.read(fetched.path)) == before
    explicit = fetched.model_copy(
        update={"asset": fetched.asset.model_copy(update={"id": "ambiguous.gz"})}
    )
    with pytest.raises(UnsupportedFormat):
        explicit.open()
    assert len(explicit.open(reader="csv", nrows=1)) == 1


def test_owned_client_can_reopen_and_injected_client_remains_open() -> None:
    dataset = default_registry().get("noaa:storm-events")
    query = build_query(start="1950-01-01", end="1950-12-31")
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing((NAME, "10508")))
        own = StormEvents(dataset)
        with own:
            own.list_assets(query)
            client = own._client
        assert client is not None and client.is_closed
        with own:
            own.list_assets(query)
            assert own._client is not client
        with httpx.Client() as injected, StormEvents(dataset, client=injected) as adapter:
            adapter.list_assets(query)
            adapter.close()
            assert not injected.is_closed


def test_cli_dry_run_and_rejected_geographic_filter() -> None:
    runner = CliRunner()
    args = [
        "fetch",
        "noaa:storm-events",
        "--start",
        "1950-04-01",
        "--end",
        "1950-04-30",
        "--dry-run",
    ]
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing((NAME, "10508")))
        result = runner.invoke(app, args)
    assert result.exit_code == 0 and result.stdout == f"{NAME}\t{URL}\n"
    with respx.mock() as mock:
        bad = runner.invoke(app, [*args, "--location", "OK"])
    assert bad.exit_code == 2 and "filter locally" in bad.output and not mock.calls


@pytest.mark.l2
def test_corrupt_gzip_propagates_failure_and_closes_local_file(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("pandas")
    dataset = default_registry().get("noaa:storm-events")
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing((NAME, str(len(GZIP)))))
        mock.get(URL).respond(200, content=GZIP)
        (item,) = fetch(dataset, build_query(start="1950-01-01", end="1950-12-31"), root=tmp_path)
    corrupt = GZIP[:8]
    item.path.write_bytes(corrupt)
    opened = []
    original_open = Path.open

    def track_open(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        opened.append(stream)
        return stream

    with monkeypatch.context() as patch, respx.mock() as mock:
        patch.setattr(Path, "open", track_open)
        with pytest.raises(EOFError):
            item.open()
        assert not mock.calls
    assert opened and all(stream.closed for stream in opened)
    assert item.path.read_bytes() == corrupt
