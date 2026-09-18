from __future__ import annotations

import math
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata import fetch, provenance
from usdata.cache import sha256_file
from usdata.cli import app
from usdata.models import Protocol, Query
from usdata.providers.base import QueryError
from usdata.providers.noaa.ibtracs import DIRECTORY_URL, Ibtracs, IbtracsParams
from usdata.pull import UpstreamChanged, pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.l2

FIXTURE = Path(__file__).parents[1] / "fixtures" / "ibtracs-na-excerpt.csv"
TEXT = FIXTURE.read_bytes()
CSV_URL = DIRECTORY_URL + "v04r01/access/csv/"
NETCDF_URL = DIRECTORY_URL + "v04r01/access/netcdf/"
NA_CSV = "ibtracs.NA.list.v04r01.csv"
NA_NETCDF = "IBTrACS.NA.v04r01.nc"
URL = CSV_URL + NA_CSV
MANIFEST = """name: tracks
sources:
  - dataset: noaa:ibtracs
    params:
      subset: na
"""


def listing(*entries: str | tuple[str, int]) -> str:
    rows = []
    for entry in entries:
        name, size = entry if isinstance(entry, tuple) else (entry, None)
        rows.append(
            f'<tr><td><a href="{name}">{name}</a></td><td align="right">2026-09-17 09:02</td>'
            f'<td align="right">{"-" if size is None else size}</td><td> </td></tr>'
        )
    return "<table><tbody>" + "".join(rows) + "</tbody></table>"


VERSIONS = listing("v03r09", "v04r00", "v04r01")


def mock_archive(mock: respx.MockRouter, *, versions: str = VERSIONS) -> None:
    mock.get(DIRECTORY_URL).respond(200, text=versions)
    mock.get(CSV_URL).respond(
        200, text=listing((NA_CSV, len(TEXT)), ("ibtracs.SA.list.v04r01.csv", 56442))
    )
    mock.get(NETCDF_URL).respond(200, text=listing((NA_NETCDF, 4245681)))


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield Ibtracs(default_registry().get("noaa:ibtracs"), client=client)


def test_selects_the_named_subset_from_the_newest_version(adapter) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_archive(mock)
        (asset,) = adapter.list_assets(build_query(subset="NA"))
        assert mock.calls.call_count == 2  # The version listing, then the csv directory.
    assert asset.id == NA_CSV and asset.href == URL
    assert asset.protocol is Protocol.HTTP and asset.media_type == "text/csv"
    assert asset.size == len(TEXT)  # NCEI lists exact byte sizes.
    # The bounds are the archive's first record and the build stamp NCEI lists, read as UTC.
    assert asset.time.start.isoformat() == "1842-10-25T03:00:00+00:00"
    assert asset.time.end.isoformat() == "2026-09-17T09:02:00+00:00"


def test_period_subsets_carry_their_defining_start(adapter) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_archive(mock)
        mock.get(CSV_URL).respond(
            200,
            text=listing(
                ("ibtracs.since1980.list.v04r01.csv", 3),
                ("ibtracs.last3years.list.v04r01.csv", 2),
                ("ibtracs.ACTIVE.list.v04r01.csv", 1),
            ),
        )
        (since,) = adapter.list_assets(build_query(subset="since1980"))
        (recent,) = adapter.list_assets(build_query(subset="last3years"))
        (active,) = adapter.list_assets(build_query(subset="active"))
    assert since.time.start.isoformat() == "1980-01-01T00:00:00+00:00"
    assert recent.time.start.isoformat() == "2023-01-01T00:00:00+00:00"
    assert active.time.start.isoformat() == "1842-10-25T03:00:00+00:00"
    assert {a.time.end.isoformat() for a in (since, recent, active)} == {
        "2026-09-17T09:02:00+00:00"
    }


def test_a_listing_without_a_stamp_leaves_the_end_open(adapter) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_archive(mock)
        mock.get(CSV_URL).respond(
            200,
            text='<table><tr><td><a href="ibtracs.last3years.list.v04r01.csv">x</a></td>'
            "<td>-</td></tr></table>",
        )
        (asset,) = adapter.list_assets(build_query(subset="last3years"))
    assert asset.size is None and asset.time.end is None
    assert asset.time.start.isoformat() == "1842-10-25T03:00:00+00:00"


def test_versions_order_numerically_and_per_storm_layouts_are_skipped(adapter) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_archive(mock, versions=listing("v04r01", "v10r00/", "v04r00", "v03r09", "v02r01"))
        mock.get(DIRECTORY_URL + "v10r00/access/csv/").respond(
            200, text=listing(("ibtracs.NA.list.v10r00.csv", 1))
        )
        (asset,) = adapter.list_assets(build_query(subset="na"))
    assert asset.id == "ibtracs.NA.list.v10r00.csv"
    with respx.mock(assert_all_called=False) as mock:
        mock_archive(mock, versions=listing("v03r09", "archive/", "README.txt"))
        with pytest.raises(QueryError, match="no IBTrACS product version"):
            adapter.list_assets(build_query(subset="na"))


def test_a_pinned_version_skips_the_version_listing(adapter) -> None:
    older = DIRECTORY_URL + "v04r00/access/csv/"
    with respx.mock() as mock:
        route = mock.get(older).respond(200, text=listing(("ibtracs.NA.list.v04r00.csv", 7)))
        (asset,) = adapter.list_assets(build_query(subset="na", version="V04R00"))
        assert route.call_count == 1 and mock.calls.call_count == 1
    assert asset.id == "ibtracs.NA.list.v04r00.csv" and asset.size == 7


def test_netcdf_format_names_the_other_directory_and_media_type(adapter) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_archive(mock)
        (asset,) = adapter.list_assets(build_query(subset="na", format="netcdf"))
    assert asset.id == NA_NETCDF and asset.href == NETCDF_URL + NA_NETCDF
    assert asset.media_type == "application/x-netcdf" and asset.size == 4245681


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("all", "all"),
        ("ALL", "all"),
        (" Active ", "active"),
        ("last3years", "last3years"),
        ("SINCE1980", "since1980"),
        ("NA", "na"),
        ("wp", "wp"),
    ],
)
def test_subset_folds_case_and_surrounding_space(adapter, raw, expected) -> None:
    assert adapter.parse_params(Query(params={"subset": raw}), IbtracsParams).subset == expected


@pytest.mark.parametrize("raw", ["atlantic", "", 1, None, ["na"], "n a"])
def test_subset_names_the_eleven_files_and_echoes_the_rejected_value(adapter, raw) -> None:
    with pytest.raises(QueryError) as raised:
        adapter.parse_params(Query(params={"subset": raw}), IbtracsParams)
    assert str(raised.value) == (
        "subset must be one of all, active, last3years, since1980, na, ep, wp, ni, si, sp, "
        f"sa, not {raw!r}"
    )


def test_subset_is_required(adapter) -> None:
    with pytest.raises(QueryError, match="subset is required: subset: all, active"):
        adapter.parse_params(Query(params={}), IbtracsParams)


@pytest.mark.parametrize("raw", ["shapefile", "CSV", "", 1])
def test_format_names_the_two_readers_cover(adapter, raw) -> None:
    with pytest.raises(QueryError, match="format must be csv or netcdf"):
        adapter.parse_params(Query(params={"subset": "na", "format": raw}), IbtracsParams)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("4.1", "version must be a product version such as v04r01, not '4.1'"),
        ("v4r1", "version must be a product version such as v04r01, not 'v4r1'"),
        (401, "version must be a product version such as v04r01, not 401"),
        ("v03r09", "version must be v04r00 or later; v03r09 publishes one file per storm"),
    ],
)
def test_version_is_a_directory_name_from_the_per_subset_era(adapter, raw, message) -> None:
    with pytest.raises(QueryError, match=message):
        adapter.parse_params(Query(params={"subset": "na", "version": raw}), IbtracsParams)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start": "2021-01-01", "end": "2021-12-31"},
        {"start": "2021-01-01"},
        {"end": "2021-12-31"},
        {"location": "FL"},
        {"variables": ["USA_WIND"]},
        {"text": "ida"},
        {"basin": "na"},
        {"year": 2021},
    ],
)
def test_rejects_unsupported_queries_before_network(adapter, kwargs) -> None:
    with respx.mock() as mock, pytest.raises(QueryError):
        adapter.list_assets(build_query(subset="na", **kwargs))
    assert not mock.calls


def test_rejected_dates_point_at_the_period_subsets(adapter) -> None:
    with pytest.raises(QueryError, match="since1980 or last3years"):
        adapter.list_assets(build_query(subset="all", start="2021-01-01", end="2021-12-31"))


def test_missing_file_is_an_error_not_a_silent_fallback(adapter) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_archive(mock)
        with pytest.raises(
            QueryError, match=r"no ibtracs\.WP\.list\.v04r01\.csv in the IBTrACS v04r01"
        ):
            adapter.list_assets(build_query(subset="wp"))


def test_listing_http_errors_surface(adapter) -> None:
    with respx.mock() as mock:
        mock.get(DIRECTORY_URL).respond(404)
        with pytest.raises(httpx.HTTPStatusError):
            adapter.list_assets(build_query(subset="na"))


def test_fetch_preserves_bytes_and_reuses_the_cache(tmp_path: Path) -> None:
    dataset = default_registry().get("noaa:ibtracs")
    with respx.mock(assert_all_called=False) as mock:
        mock_archive(mock)
        data = mock.get(URL).respond(200, content=TEXT)
        (first,) = fetch(dataset, build_query(subset="na"), root=tmp_path)
        (cached,) = fetch(dataset, build_query(subset="NA"), root=tmp_path)
    assert first.path.read_bytes() == TEXT and first.provenance.size == len(TEXT)
    assert first.provenance.checksum == sha256_file(first.path)
    assert first.provenance.transformations == []
    assert cached.from_cache and data.call_count == 1


def test_locked_restore_pins_the_bytes_and_reports_an_in_place_rebuild(tmp_path: Path) -> None:
    """The file keeps its name when NCEI rebuilds it, so the checksum is the pin."""
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    rebuilt = TEXT + b"2026252N12300,2026,9,NA,MM,UNNAMED,2026-09-09 00:00:00\n"
    with respx.mock(assert_all_called=False) as mock:
        mock_archive(mock)
        mock.get(URL).respond(200, content=TEXT)
        initial = pull(manifest, root=tmp_path)
    path = initial.fetched[0].path
    path.unlink()
    with respx.mock(assert_all_called=False) as mock:
        versions = mock.get(DIRECTORY_URL).respond(200, text=VERSIONS)
        mock.get(URL).respond(200, content=TEXT)
        restored = pull(manifest, root=tmp_path)
        assert not versions.called  # A lockfile restores its pinned URL without listing.
    assert restored.fetched[0].asset.id == NA_CSV and verify(manifest, root=tmp_path) == []
    path.unlink()
    with respx.mock() as mock:
        mock.get(URL).respond(200, content=rebuilt)
        with pytest.raises(UpstreamChanged) as raised:
            pull(manifest, root=tmp_path)
    assert [d.problem for d in raised.value.drift] == ["upstream changed"]
    assert not path.exists()
    with respx.mock() as mock:
        mock.get(URL).respond(200, content=rebuilt)
        updated = pull(manifest, root=tmp_path, update=["noaa:ibtracs"])
    assert updated.fetched[0].asset.id == NA_CSV and path.read_bytes() == rebuilt
    assert updated.fetched[0].provenance.checksum == sha256_file(path)
    assert verify(manifest, root=tmp_path) == []


@pytest.fixture
def tracks(tmp_path: Path):
    pytest.importorskip("pandas")
    with respx.mock(assert_all_called=False) as mock:
        mock_archive(mock)
        mock.get(URL).respond(200, content=TEXT)
        (fetched,) = fetch(
            default_registry().get("noaa:ibtracs"), build_query(subset="na"), root=tmp_path
        )
    return fetched


def test_reader_keeps_the_units_row_and_reads_a_space_as_missing(tracks) -> None:
    before = tracks.path.read_bytes(), provenance.read(tracks.path)
    with respx.mock() as mock:
        frame = tracks.open()
        assert not mock.calls
    assert len(frame) == 13 and list(frame.columns[:7]) == [
        "SID",
        "SEASON",
        "NUMBER",
        "BASIN",
        "SUBBASIN",
        "NAME",
        "ISO_TIME",
    ]
    assert frame.attrs["units"]["USA_WIND"] == "kts" and frame.attrs["units"]["SID"] == ""
    assert frame.attrs["units"]["LAT"] == "degrees_north"
    # The single space NCEI writes for a missing value is missing, so measurements are numeric.
    assert str(frame.USA_WIND.dtype) == "int64" and str(frame.WMO_WIND.dtype) == "float64"
    assert frame.USA_RECORD.isna().sum() == 12 and frame.USA_RECORD.dropna().tolist() == ["L"]
    assert (tracks.path.read_bytes(), provenance.read(tracks.path)) == before
    assert frame.attrs["usdata"]["asset_id"] == NA_CSV
    assert frame.attrs["usdata"]["provenance"]["checksum"] == before[1].checksum


def test_reader_keeps_the_north_atlantic_basin_code_as_text(tracks) -> None:
    """pandas reads ``NA`` as missing by default, which would erase the basin itself."""
    frame = tracks.open()
    assert frame.BASIN.tolist() == ["NA", "NA", "EP", "EP", "EP"] + ["NA"] * 8
    assert frame.BASIN.notna().all() and frame.NAME.tolist()[:2] == ["UNNAMED", "UNNAMED"]
    assert frame.SUBBASIN.tolist()[:3] == ["NA", "NA", "MM"]  # The sub-basin is also ``NA``.


def test_reader_options_still_apply(tracks) -> None:
    frame = tracks.open(parse_dates=["ISO_TIME"], usecols=["SID", "ISO_TIME", "USA_SSHS"], nrows=6)
    assert list(frame.columns) == ["SID", "ISO_TIME", "USA_SSHS"] and len(frame) == 6
    assert str(frame.ISO_TIME.dtype).startswith("datetime64")
    assert frame.ISO_TIME.iloc[-1].isoformat() == "2021-08-29T03:00:00"
    assert frame.USA_SSHS.tolist() == [0, 0, 0, 0, 0, 3]
    landfall = tracks.open()
    ida = landfall[landfall.SID == "2021239N17281"]
    assert ida.USA_SSHS.max() == 4 and math.isnan(ida.WMO_WIND.max()) is False
    assert (ida.LANDFALL == 0).sum() == 4


def test_owned_client_can_reopen_and_injected_client_remains_open() -> None:
    dataset = default_registry().get("noaa:ibtracs")
    with respx.mock(assert_all_called=False) as mock:
        mock_archive(mock)
        own = Ibtracs(dataset)
        with own:
            own.list_assets(build_query(subset="na"))
            client = own._client
        assert client is not None and client.is_closed
        with own:
            own.list_assets(build_query(subset="na"))
            assert own._client is not client
        with httpx.Client() as injected, Ibtracs(dataset, client=injected) as adapter:
            adapter.list_assets(build_query(subset="na"))
            adapter.close()
            assert not injected.is_closed


def test_cli_dry_run_and_rejected_date_filter() -> None:
    runner = CliRunner()
    with respx.mock(assert_all_called=False) as mock:
        mock_archive(mock)
        result = runner.invoke(app, ["fetch", "noaa:ibtracs", "--dry-run", "-p", "subset=na"])
    assert result.exit_code == 0 and result.stdout == f"{NA_CSV}\t{len(TEXT)}\t{URL}\n"
    with respx.mock() as mock:
        bad = runner.invoke(
            app, ["fetch", "noaa:ibtracs", "--dry-run", "-p", "subset=na", "--start", "2021-01-01"]
        )
    assert bad.exit_code == 2 and "since1980 or last3years" in bad.output and not mock.calls
