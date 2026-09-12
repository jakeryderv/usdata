from __future__ import annotations

import math
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
from usdata.providers.noaa.hurdat2 import DIRECTORY_URL, Hurdat2
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.l2

FIXTURE = Path(__file__).parents[1] / "fixtures" / "hurdat2-atlantic-excerpt.txt"
TEXT = FIXTURE.read_bytes()
ATLANTIC = "hurdat2-1851-2025-02272026.txt"
PACIFIC = "hurdat2-nepac-1949-2025-02272026.txt"
URL = DIRECTORY_URL + ATLANTIC
MANIFEST = """name: tracks
sources:
  - dataset: noaa:hurdat2
    params:
      basin: atlantic
"""


def listing(*names: str) -> str:
    return (
        "<table>"
        + "".join(
            f'<tr><td><img src="/icons/text.gif"></td><td><a href="{name}">{name}</a></td>'
            f'<td align="right">2026-03-05 16:03</td><td align="right">6.8M</td></tr>'
            for name in names
        )
        + "</table>"
    )


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield Hurdat2(default_registry().get("noaa:hurdat2"), client=client)


def test_selects_newest_span_and_revision_ignoring_other_names(adapter) -> None:
    with respx.mock() as mock:
        route = mock.get(DIRECTORY_URL).respond(
            200,
            text=listing(
                "hurdat2-1851-2017-050118.txt",  # MMDDYY revision, older span
                "hurdat2-atl-1851-2023-042624.txt",  # explicit Atlantic basin token
                "hurdat2-1851-2023-051124.txt",  # newer revision of the same span
                ATLANTIC,
                "hurdat2-1851-2025-13322026.txt",  # not a real revision date
                PACIFIC,
                "hurdat2-atl-02052024.txt",  # no data span in the name
                "../" + ATLANTIC,
                "https://example.test/" + ATLANTIC,
            ),
        )
        (asset,) = adapter.list_assets(build_query())
        assert route.call_count == 1
    assert asset.id == ATLANTIC and asset.href == URL
    assert asset.protocol is Protocol.HTTP and asset.media_type == "text/plain"
    assert asset.size is None  # The listing reports approximate sizes such as "6.8M".
    assert asset.time.start.isoformat() == "1851-01-01T00:00:00+00:00"
    assert asset.time.end.isoformat() == "2025-12-31T23:59:59.999999+00:00"


def test_basin_selects_a_different_file_and_span(adapter) -> None:
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing(ATLANTIC, PACIFIC))
        (pacific,) = adapter.list_assets(build_query(basin="Pacific"))
        (default,) = adapter.list_assets(build_query())
        (repeated,) = adapter.list_assets(build_query(basin="atlantic"))
    assert pacific.id == PACIFIC and pacific.time.start.year == 1949
    assert default.id == ATLANTIC and default == repeated


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start": "2021-01-01", "end": "2021-12-31"},
        {"start": "2021-01-01"},
        {"end": "2021-12-31"},
        {"location": "FL"},
        {"variables": ["max_wind_kt"]},
        {"text": "ida"},
        {"basin": "gulf"},
        {"basin": ""},
        {"basin": 1},
        {"year": 2021},
        {"storm": "AL092021"},
    ],
)
def test_rejects_unsupported_queries_before_network(adapter, kwargs) -> None:
    with respx.mock() as mock, pytest.raises(QueryError):
        adapter.list_assets(build_query(**kwargs))
    assert not mock.calls


def test_rejected_dates_explain_that_the_file_is_complete(adapter) -> None:
    with pytest.raises(QueryError, match="complete basin"):
        adapter.list_assets(build_query(start="2021-01-01", end="2021-12-31"))


def test_missing_basin_file_is_an_error_not_a_silent_fallback(adapter) -> None:
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing(ATLANTIC))
        with pytest.raises(QueryError, match="pacific"):
            adapter.list_assets(build_query(basin="pacific"))
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text="<html>unavailable</html>")
        with pytest.raises(QueryError, match="atlantic"):
            adapter.list_assets(build_query())


def test_listing_http_errors_surface(adapter) -> None:
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(404)
        with pytest.raises(httpx.HTTPStatusError):
            adapter.list_assets(build_query())


def test_fetch_preserves_text_bytes_and_reuses_the_cache(tmp_path: Path) -> None:
    dataset = default_registry().get("noaa:hurdat2")
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing(ATLANTIC))
        data = mock.get(URL).respond(200, content=TEXT)
        (first,) = fetch(dataset, build_query(), root=tmp_path)
        (cached,) = fetch(dataset, build_query(basin="atlantic"), root=tmp_path)
    assert first.path.read_bytes() == TEXT and first.provenance.size == len(TEXT)
    assert first.provenance.checksum == sha256_file(first.path)
    assert first.provenance.transformations == []
    assert cached.from_cache and data.call_count == 1


def test_locked_restore_pins_the_revision_and_rejects_changed_bytes(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    newer = "hurdat2-1851-2026-03012027.txt"
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing(ATLANTIC))
        mock.get(URL).respond(200, content=TEXT)
        initial = pull(manifest, root=tmp_path)
    path = initial.fetched[0].path
    path.unlink()
    with respx.mock(assert_all_called=False) as mock:
        directory = mock.get(DIRECTORY_URL).respond(200, text=listing(newer))
        old = mock.get(URL).respond(200, content=TEXT)
        restored = pull(manifest, root=tmp_path)
    assert old.called and not directory.called
    assert restored.fetched[0].asset.id == ATLANTIC and verify(manifest, root=tmp_path) == []
    path.unlink()
    with respx.mock() as mock:
        mock.get(URL).respond(200, content=TEXT + b"\n")
        with pytest.raises(ChecksumMismatch):
            pull(manifest, root=tmp_path)
    assert not path.exists()
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing(ATLANTIC, newer))
        mock.get(DIRECTORY_URL + newer).respond(200, content=TEXT)
        updated = pull(manifest, root=tmp_path, force=True)
    assert updated.fetched[0].asset.id == newer and updated.fetched[0].path != path


@pytest.fixture
def tracks(tmp_path: Path):
    pytest.importorskip("pandas")
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing(ATLANTIC))
        mock.get(URL).respond(200, content=TEXT)
        (fetched,) = fetch(default_registry().get("noaa:hurdat2"), build_query(), root=tmp_path)
    return fetched


def test_reader_is_inferred_local_and_tidy(tracks) -> None:
    before = tracks.path.read_bytes(), provenance.read(tracks.path)
    with respx.mock() as mock:
        frame = tracks.open()
        assert not mock.calls
    assert len(frame) == 27  # Four storms: 14 + 1 + 5 + 7 declared track points.
    assert frame.storm_id.nunique() == 4
    assert list(frame.columns[:5]) == ["storm_id", "name", "time", "record_identifier", "status"]
    assert str(frame.time.dtype).endswith(", UTC]")  # Timezone-aware, pandas resolution.
    assert str(frame.storm_id.dtype).startswith("string")
    assert (tracks.path.read_bytes(), provenance.read(tracks.path)) == before
    assert frame.attrs["usdata"]["asset_id"] == ATLANTIC
    assert frame.attrs["usdata"]["provenance"]["checksum"] == before[1].checksum


def test_reader_signs_coordinates_and_converts_missing_sentinels(tracks) -> None:
    frame = tracks.open()
    first = frame.iloc[0]
    assert first.storm_id == "AL011851" and first["name"] == "UNNAMED"
    assert first.time.isoformat() == "1851-06-25T00:00:00+00:00"
    assert (first.latitude, first.longitude) == (28.0, -94.8)  # 28.0N, 94.8W
    assert first.max_wind_kt == 80.0 and math.isnan(first.min_pressure_mb)
    assert frame.filter(like="_nm").iloc[0].isna().all()  # Radii predate 2004.
    assert first.status == "HU" and frame.record_identifier.isna().iloc[0]
    landfall = frame[frame.record_identifier == "L"]
    assert list(landfall.time.dt.strftime("%Y-%m-%dT%H:%M")) == [
        "1851-06-25T21:00",
        "2021-06-28T23:20",
    ]
    # -99 is the documented unassigned intensity of a 1967-era depression.
    unassigned = frame[frame.storm_id == "AL021971"].iloc[-1]
    assert math.isnan(unassigned.max_wind_kt)
    modern = frame[frame.storm_id == "AL042021"].iloc[2]
    assert (modern.r34_ne_nm, modern.r34_se_nm, modern.r64_nw_nm) == (40.0, 0.0, 0.0)
    assert modern.max_wind_radius_nm == 40.0 and modern.min_pressure_mb == 1011.0


def test_reader_is_inferred_from_an_archived_filename_alone(tracks) -> None:
    archived = tracks.model_copy(
        update={"asset": tracks.asset.model_copy(update={"dataset_id": "noaa:storm-events"})}
    )
    assert len(archived.open()) == 27


def test_reader_rejects_csv_options(tracks) -> None:
    with pytest.raises(ValueError, match="apply only to CSV readers"):
        tracks.open(nrows=1)


def test_owned_client_can_reopen_and_injected_client_remains_open() -> None:
    dataset = default_registry().get("noaa:hurdat2")
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing(ATLANTIC))
        own = Hurdat2(dataset)
        with own:
            own.list_assets(build_query())
            client = own._client
        assert client is not None and client.is_closed
        with own:
            own.list_assets(build_query())
            assert own._client is not client
        with httpx.Client() as injected, Hurdat2(dataset, client=injected) as adapter:
            adapter.list_assets(build_query())
            adapter.close()
            assert not injected.is_closed


def test_cli_dry_run_and_rejected_date_filter() -> None:
    runner = CliRunner()
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(200, text=listing(ATLANTIC, PACIFIC))
        result = runner.invoke(app, ["fetch", "noaa:hurdat2", "--dry-run"])
    assert result.exit_code == 0 and result.stdout == f"{ATLANTIC}\t{URL}\n"
    with respx.mock() as mock:
        bad = runner.invoke(app, ["fetch", "noaa:hurdat2", "--dry-run", "--start", "2021-01-01"])
    assert bad.exit_code == 2 and "complete basin" in bad.output and not mock.calls
