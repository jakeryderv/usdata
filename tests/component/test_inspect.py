"""Format-aware summaries: CSV without an extra, NetCDF and GRIB2 with theirs, and the CLI."""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from usdata import FetchedAsset, inspect_asset, inspect_path
from usdata.cache import cached_path, sha256_file
from usdata.cli import app
from usdata.inspect import AssetFormat, CsvSummary, NetcdfSummary
from usdata.models import Asset, ByteRange, Protocol, Provenance
from usdata.provenance import write

NETCDF_FIXTURE = Path(__file__).parents[1] / "fixtures/netcdf/packed-grid.nc"
CSV = b"time,station,value\n2024-05-06,USW00013967,1.0\n2024-05-07,USW00013967,2.0\n"

runner = CliRunner()


def grib_ranges(content: bytes) -> list[ByteRange]:
    """One inclusive byte range per GRIB2 message, as a partial fetch records them."""
    ranges: list[ByteRange] = []
    offset = 0
    while offset < len(content):
        length = int.from_bytes(content[offset + 8 : offset + 16], "big")
        ranges.append(ByteRange(start=offset, end=offset + length - 1))
        offset += length
    return ranges


def cached(
    tmp_path: Path,
    name: str,
    content: bytes,
    *,
    media_type: str | None = None,
    dataset_id: str = "noaa:ghcn-daily",
    protocol: Protocol = Protocol.HTTP,
    sidecar: bool = True,
    messages: list[int] | None = None,
    selectors: list[str] | None = None,
) -> FetchedAsset:
    """One asset on disk with the provenance sidecar a real fetch writes beside it.

    With ``messages``, the sidecar is the one a partial GRIB2 fetch writes: the
    source object's message numbers in the href fragment and one recorded byte
    range per message.
    """
    path = tmp_path / name
    href = f"https://example.test/{name}"
    path.write_bytes(content)
    partial: dict[str, Any] = {}
    if messages is not None:
        numbers = ",".join(str(number) for number in messages)
        href = f"{href}#messages={numbers}"
        partial = {
            "transformations": [
                f"grib2 messages {numbers} concatenated from https://example.test/{name}"
            ],
            "index_url": f"https://example.test/{name}.idx",
            "index_checksum": "sha256:" + "0" * 64,
            "ranges": grib_ranges(content),
            "selectors": selectors or [],
            "object_size": 151_717_165,
            "object_etag": "81198a73ad430c73adfbe3335421ea99",
        }
    asset = Asset(
        id=name,
        dataset_id=dataset_id,
        href=href,
        protocol=protocol,
        media_type=media_type,
    )
    record = Provenance(
        dataset_id=dataset_id,
        provider=dataset_id.partition(":")[0],
        source_url=asset.href,
        retrieved_at=datetime(2026, 9, 15, tzinfo=UTC),
        checksum=sha256_file(path),
        size=path.stat().st_size,
        usdata_version="0.16.0",
        **partial,
    )
    if sidecar:
        write(record, path)
    return FetchedAsset(asset=asset, path=path, provenance=record, from_cache=True)


def test_csv_columns_and_row_count_need_no_extra(tmp_path: Path) -> None:
    fetched = cached(tmp_path, "daily.csv", CSV, media_type="text/csv")
    summary = fetched.inspect()
    assert summary.format is AssetFormat.CSV
    assert summary.dataset_id == "noaa:ghcn-daily" and summary.asset_id == "daily.csv"
    assert summary.size == len(CSV) and summary.checksum == fetched.provenance.checksum
    assert summary.source_url == "https://example.test/daily.csv"
    assert summary.retrieved_at == datetime(2026, 9, 15, tzinfo=UTC)
    assert isinstance(summary.detail, CsvSummary)
    assert summary.csv is not None
    assert summary.csv.columns == ["time", "station", "value"]
    assert (summary.csv.row_count, summary.csv.truncated) == (2, False)
    assert summary.note is None


UNITS_CSV = b"time,latitude,sst\nUTC,degrees_north,degree_C\n2024-05-06T00:00:00Z,35.0,21.5\n"


def test_a_units_row_is_reported_as_units_and_not_counted_as_data(tmp_path: Path) -> None:
    served = cached(tmp_path, "sst.csv", UNITS_CSV, media_type="text/csv", protocol=Protocol.ERDDAP)
    summary = served.inspect()
    assert summary.csv is not None
    assert summary.csv.units == {"time": "UTC", "latitude": "degrees_north", "sst": "degree_C"}
    assert summary.csv.row_count == 1
    # The same bytes over plain HTTP have no units row, so every line under the header is data.
    plain = cached(tmp_path, "plain.csv", UNITS_CSV, media_type="text/csv").inspect()
    assert plain.csv is not None and plain.csv.units == {} and plain.csv.row_count == 2


def test_inspect_counts_the_rows_open_returns_for_ibtracs(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    content = (Path(__file__).parents[1] / "fixtures/ibtracs-na-excerpt.csv").read_bytes()
    fetched = cached(
        tmp_path, "ibtracs.csv", content, media_type="text/csv", dataset_id="noaa:ibtracs"
    )
    summary = fetched.inspect()
    assert summary.csv is not None
    assert summary.csv.row_count == len(fetched.open())
    assert summary.csv.units["SEASON"] == "Year"


def test_inspect_path_learns_the_units_row_from_the_registry(tmp_path: Path) -> None:
    # A sidecar records no protocol; the dataset it names is served over ERDDAP.
    cached(tmp_path, "sst.csv", UNITS_CSV, dataset_id="noaa:coastwatch-sst")
    summary = inspect_path(tmp_path / "sst.csv")
    assert summary.csv is not None
    assert summary.csv.row_count == 1 and summary.csv.units["sst"] == "degree_C"
    # A dataset the registry does not know is summarized as a plain CSV, not refused.
    cached(tmp_path, "other.csv", UNITS_CSV, dataset_id="demo:unregistered")
    other = inspect_path(tmp_path / "other.csv")
    assert other.csv is not None and other.csv.row_count == 2 and other.note is None


def test_a_units_row_that_does_not_match_the_header_is_noted_not_raised(tmp_path: Path) -> None:
    broken = b"time,latitude,sst\nUTC,degrees_north\n"
    summary = cached(
        tmp_path, "broken.csv", broken, media_type="text/csv", protocol=Protocol.ERDDAP
    ).inspect()
    assert summary.csv is None and summary.note is not None
    assert "units row" in summary.note


def test_a_capped_csv_scan_reports_the_count_as_a_lower_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("usdata.inspect.ROW_LIMIT", 2)
    rows = b"".join(b"2024-05-%02d,USW00013967,1.0\n" % day for day in range(1, 6))
    summary = cached(tmp_path, "long.csv", b"time,station,value\n" + rows).inspect()
    assert summary.csv is not None
    assert summary.csv.row_count == 2 and summary.csv.row_limit == 2
    assert summary.csv.truncated


def test_a_gzipped_csv_is_summarized_without_changing_the_cached_bytes(tmp_path: Path) -> None:
    content = gzip.compress(CSV)
    fetched = cached(tmp_path, "daily.csv.gz", content, media_type="application/gzip")
    summary = inspect_asset(fetched)
    assert summary.format is AssetFormat.CSV
    assert summary.csv is not None and summary.csv.row_count == 2
    assert fetched.path.read_bytes() == content


@pytest.mark.parametrize("content", [b"\x1f\x8b\x07nonsense", gzip.compress(CSV)[:20]])
def test_bytes_that_no_longer_decode_are_a_note_rather_than_a_failure(
    tmp_path: Path, content: bytes
) -> None:
    fetched = cached(tmp_path, "daily.csv.gz", content, media_type="application/gzip")
    summary = fetched.inspect()
    assert summary.format is AssetFormat.CSV and summary.detail is None
    assert summary.note is not None and summary.note.startswith("not readable as csv")
    assert summary.size == len(content) and summary.dataset_id == "noaa:ghcn-daily"


@pytest.mark.parametrize("name, media_type", [("tile.tif", "image/tiff"), ("notes.txt", None)])
def test_a_format_with_no_reader_is_summarized_as_bytes(
    tmp_path: Path, name: str, media_type: str | None
) -> None:
    summary = cached(
        tmp_path, name, b"II*\x00", media_type=media_type, dataset_id="usgs:3dep"
    ).inspect()
    assert summary.format is AssetFormat.BYTES
    assert summary.detail is None and summary.note is None
    assert summary.size == 4


def test_inspect_path_reads_the_sidecar_and_infers_the_format_from_the_name(
    tmp_path: Path,
) -> None:
    fetched = cached(tmp_path, "daily.csv", CSV)
    summary = inspect_path(fetched.path)
    assert summary.format is AssetFormat.CSV
    assert summary.asset_id == "daily.csv" and summary.dataset_id == "noaa:ghcn-daily"
    assert summary.csv is not None and summary.csv.columns == ["time", "station", "value"]


def test_inspect_path_accepts_the_string_the_cli_prints(tmp_path: Path) -> None:
    """The CLI prints a plain path, so pasting one back in must not need a Path()."""
    fetched = cached(tmp_path, "daily.csv", CSV)
    assert inspect_path(str(fetched.path)) == inspect_path(fetched.path)


def test_inspect_path_without_a_sidecar_raises(tmp_path: Path) -> None:
    fetched = cached(tmp_path, "daily.csv", CSV, sidecar=False)
    with pytest.raises(OSError):
        inspect_path(fetched.path)


@pytest.mark.netcdf
def test_a_missing_extra_yields_a_note_naming_it_and_no_detail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from usdata import _netcdf

    real_import = _netcdf.import_module

    def without_xarray(name: str) -> object:
        if name == "xarray":
            raise ModuleNotFoundError("No module named 'xarray'", name="xarray")
        return real_import(name)

    monkeypatch.setattr(_netcdf, "import_module", without_xarray)
    fetched = cached(
        tmp_path,
        "scene.nc",
        NETCDF_FIXTURE.read_bytes(),
        media_type="application/x-netcdf",
        dataset_id="noaa:goes-abi",
    )
    summary = fetched.inspect()
    assert summary.format is AssetFormat.NETCDF
    assert summary.detail is None and summary.netcdf is None
    assert summary.note is not None and "usdata[netcdf]" in summary.note


@pytest.mark.netcdf
def test_netcdf_variables_carry_dims_shape_and_stated_metadata(tmp_path: Path) -> None:
    pytest.importorskip("h5netcdf")
    pytest.importorskip("h5py")
    pytest.importorskip("xarray")
    fetched = cached(
        tmp_path,
        "scene.nc",
        NETCDF_FIXTURE.read_bytes(),
        media_type="application/x-netcdf",
        dataset_id="noaa:goes-abi",
    )
    summary = fetched.inspect()
    assert isinstance(summary.detail, NetcdfSummary)
    assert summary.netcdf is not None and summary.note is None
    variables = {variable.name: variable for variable in summary.netcdf.variables}
    assert {"CMI", "DQF", "unsigned_count", "t"} <= set(variables)
    assert variables["CMI"].dims == ["y", "x"] and variables["CMI"].shape == [2, 3]
    assert variables["CMI"].units == "K"
    assert fetched.path.read_bytes() == NETCDF_FIXTURE.read_bytes()


@pytest.fixture
def grib(tmp_path: Path) -> FetchedAsset:
    """Three synthetic messages on one grid, the file the reader demands a select for."""
    ec = pytest.importorskip("eccodes")
    np = pytest.importorskip("numpy")
    pytest.importorskip("xarray")

    def message(value: float, *, param: int, level_type: str, level: int) -> bytes:
        handle = ec.codes_grib_new_from_samples("regular_ll_sfc_grib2")
        try:
            for key, setting in (("Ni", 4), ("Nj", 3)):
                ec.codes_set(handle, key, setting)
            ec.codes_set(handle, "typeOfLevel", level_type)
            ec.codes_set(handle, "level", level)
            ec.codes_set(handle, "paramId", param)
            ec.codes_set(handle, "packingType", "grid_simple")
            ec.codes_set_values(handle, np.full(12, value))
            return ec.codes_get_message(handle)
        finally:
            ec.codes_release(handle)

    parts = [
        message(500.0, param=130, level_type="isobaricInhPa", level=500),
        message(850.0, param=130, level_type="isobaricInhPa", level=850),
        message(7.0, param=59, level_type="surface", level=0),
    ]
    return cached(
        tmp_path,
        "multi.grib2",
        b"".join(parts),
        media_type="application/x-grib2",
        dataset_id="noaa:hrrr",
    )


@pytest.mark.grib
def test_grib2_messages_are_listed_with_the_keys_select_matches(grib: FetchedAsset) -> None:
    summary = grib.inspect()
    assert summary.format is AssetFormat.GRIB2
    assert summary.grib2 is not None and summary.note is None
    messages = summary.grib2.messages
    assert [message.file_index for message in messages] == [0, 1, 2]
    assert [message.object_index for message in messages] == [None, None, None]
    assert [message.short_name for message in messages] == ["t", "t", "cape"]
    assert [message.level for message in messages] == ["500", "850", "0"]
    assert messages[0].type_of_level == "isobaricInhPa" and messages[0].units == "K"
    assert messages[0].name == "Temperature" and messages[0].shape == (3, 4)
    assert messages[2].type_of_level == "entireAtmosphere"


@pytest.fixture
def partial_grib(tmp_path: Path) -> FetchedAsset:
    """Two messages taken from a 170-message object, as a partial fetch leaves them."""
    ec = pytest.importorskip("eccodes")
    np = pytest.importorskip("numpy")
    pytest.importorskip("xarray")

    def message(value: float, *, param: int, level_type: str, level: int) -> bytes:
        handle = ec.codes_grib_new_from_samples("regular_ll_sfc_grib2")
        try:
            for key, setting in (("Ni", 4), ("Nj", 3)):
                ec.codes_set(handle, key, setting)
            ec.codes_set(handle, "typeOfLevel", level_type)
            ec.codes_set(handle, "level", level)
            ec.codes_set(handle, "paramId", param)
            ec.codes_set(handle, "packingType", "grid_simple")
            ec.codes_set_values(handle, np.full(12, value))
            return ec.codes_get_message(handle)
        finally:
            ec.codes_release(handle)

    parts = [
        message(1500.0, param=59, level_type="surface", level=0),
        message(288.0, param=130, level_type="heightAboveGround", level=2),
    ]
    return cached(
        tmp_path,
        "part.grib2",
        b"".join(parts),
        media_type="application/x-grib2",
        dataset_id="noaa:hrrr",
        messages=[105, 131],
        selectors=["CAPE:surface", "TMP:2 m above ground"],
    )


@pytest.mark.grib
def test_a_partial_file_also_numbers_each_message_in_the_source_object(
    partial_grib: FetchedAsset,
) -> None:
    summary = partial_grib.inspect()
    assert summary.grib2 is not None
    messages = summary.grib2.messages
    assert [message.file_index for message in messages] == [0, 1]
    assert [message.object_index for message in messages] == [105, 131]
    assert [message.selector for message in messages] == ["CAPE:surface", "TMP:2 m above ground"]


@pytest.mark.grib
def test_variable_for_answers_in_the_readers_vocabulary(partial_grib: FetchedAsset) -> None:
    """Selector in, variable name out, for both halves of the naming rule."""
    spanning = partial_grib.inspect().grib2
    assert spanning is not None
    # Two level types, so every name is suffixed.
    assert spanning.variable_for("CAPE:surface") == "cape_entireAtmosphere_0"
    assert list(partial_grib.open().data_vars) == [
        spanning.variable_for("CAPE:surface"),
        spanning.variable_for("TMP:2 m above ground"),
    ]


@pytest.mark.grib
def test_variable_for_keeps_the_bare_name_when_one_level_is_spanned(
    tmp_path: Path, partial_grib: FetchedAsset
) -> None:
    ec = pytest.importorskip("eccodes")
    np = pytest.importorskip("numpy")
    messages = []
    for param in (130, 157):
        handle = ec.codes_grib_new_from_samples("regular_ll_sfc_grib2")
        try:
            for key, setting in (("Ni", 4), ("Nj", 3)):
                ec.codes_set(handle, key, setting)
            ec.codes_set(handle, "typeOfLevel", "isobaricInhPa")
            ec.codes_set(handle, "level", 500)
            ec.codes_set(handle, "paramId", param)
            ec.codes_set(handle, "packingType", "grid_simple")
            ec.codes_set_values(handle, np.full(12, 1.0))
            messages.append(ec.codes_get_message(handle))
        finally:
            ec.codes_release(handle)
    one_level = cached(
        tmp_path,
        "level.grib2",
        b"".join(messages),
        media_type="application/x-grib2",
        dataset_id="noaa:hrrr",
        messages=[12, 13],
        selectors=["TMP:500 mb", "RH:500 mb"],
    )
    summary = one_level.inspect()
    assert summary.grib2 is not None
    assert summary.grib2.variable_for("TMP:500 mb") == "t"
    assert summary.grib2.variable_for("RH:500 mb") == "r"
    assert set(one_level.open().data_vars) == {"t", "r"}


def unnamed_grib(**keys: Any) -> bytes:
    """One small message whose parameter ecCodes has no short name for."""
    ec = pytest.importorskip("eccodes")
    np = pytest.importorskip("numpy")
    handle = ec.codes_grib_new_from_samples("regular_ll_sfc_grib2")
    try:
        for key, setting in (("Ni", 4), ("Nj", 3), *keys.items()):
            ec.codes_set(handle, key, setting)
        ec.codes_set(handle, "packingType", "grid_simple")
        ec.codes_set_values(handle, np.full(12, 1.0))
        return ec.codes_get_message(handle)
    finally:
        ec.codes_release(handle)


@pytest.mark.grib
def test_variable_for_names_a_message_eccodes_cannot_name_as_the_reader_does(
    tmp_path: Path, partial_grib: FetchedAsset
) -> None:
    """The reader falls back to parameter_<d>_<c>_<n>; variable_for once used ``unknown``."""
    pytest.importorskip("xarray")
    content = partial_grib.path.read_bytes() + unnamed_grib(
        discipline=0, parameterCategory=191, parameterNumber=250
    )
    selectors = ["CAPE:surface", "TMP:2 m above ground", "var discipline=0 parm=250:surface"]
    fetched = cached(
        tmp_path,
        "unnamed.grib2",
        content,
        media_type="application/x-grib2",
        dataset_id="noaa:hrrr",
        messages=[105, 131, 140],
        selectors=selectors,
    )
    summary = fetched.inspect().grib2
    assert summary is not None
    assert summary.messages[2].short_name == "unknown"
    assert summary.messages[2].base_name == "parameter_0_191_250"
    dataset = fetched.open()
    names = [summary.variable_for(selector) for selector in selectors]
    assert names == list(dataset.data_vars)
    assert names[2] == "parameter_0_191_250_surface_0"
    messages = dataset.attrs["usdata"]["messages"]
    assert [messages[name]["selector"] for name in names] == selectors


@pytest.mark.grib
def test_an_mrms_message_is_inventoried_under_the_name_the_reader_gives_it(
    tmp_path: Path,
) -> None:
    pytest.importorskip("xarray")
    name = "MRMS_RotationTrackML30min_00.50_20240506-200000.grib2.gz"
    content = unnamed_grib(discipline=209, parameterCategory=3, parameterNumber=14)
    fetched = cached(
        tmp_path,
        name,
        gzip.compress(content),
        media_type="application/x-grib2",
        dataset_id="noaa:mrms",
    )
    summary = fetched.inspect().grib2
    assert summary is not None
    assert [message.base_name for message in summary.messages] == ["RotationTrackML30min"]
    assert list(fetched.open().data_vars) == ["RotationTrackML30min"]
    assert inspect_path(fetched.path).grib2 == summary


@pytest.mark.grib
def test_variable_for_names_the_selectors_a_file_does_hold(partial_grib: FetchedAsset) -> None:
    summary = partial_grib.inspect()
    assert summary.grib2 is not None
    with pytest.raises(KeyError, match="CAPE:surface") as error:
        summary.grib2.variable_for("cape:surface")
    assert "'cape:surface'" in str(error.value)


@pytest.mark.grib
def test_the_reader_error_lists_exactly_what_the_inventory_holds(grib: FetchedAsset) -> None:
    from usdata.readers import inventory

    messages = inventory(grib.path)
    with pytest.raises(ValueError, match=r"3 messages; pass select") as error:
        grib.open()
    for message in messages:
        triple = f"({message.short_name!r}, {message.type_of_level!r}, {message.level!r})"
        assert triple in str(error.value)


def test_the_cli_prints_the_provenance_block_and_the_column_table(tmp_path: Path) -> None:
    fetched = cached(tmp_path, "daily.csv", CSV, media_type="text/csv")
    result = runner.invoke(app, ["inspect", str(fetched.path)])
    assert result.exit_code == 0
    assert "noaa:ghcn-daily" in result.stdout and "daily.csv" in result.stdout
    assert "format:" in result.stdout and "csv" in result.stdout
    assert "rows:" in result.stdout and "columns:" in result.stdout
    assert "station" in result.stdout


def test_the_cli_emits_the_summary_as_json(tmp_path: Path) -> None:
    fetched = cached(tmp_path, "daily.csv", CSV, media_type="text/csv")
    result = runner.invoke(app, ["inspect", str(fetched.path), "--json"])
    assert result.exit_code == 0
    record = json.loads(result.stdout)
    assert record["format"] == "csv" and record["dataset_id"] == "noaa:ghcn-daily"
    assert record["csv"]["columns"] == ["time", "station", "value"]
    assert record["csv"]["row_count"] == 2 and record["netcdf"] is None


def test_the_cli_resolves_a_dataset_and_asset_id_against_the_cache(tmp_path: Path) -> None:
    path = cached_path("noaa:ghcn-daily", "daily.csv", tmp_path)
    path.parent.mkdir(parents=True)
    cached(path.parent, "daily.csv", CSV)
    result = runner.invoke(
        app, ["inspect", "noaa:ghcn-daily/daily.csv", "--cache-dir", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert "noaa:ghcn-daily" in result.stdout


def test_the_cli_says_a_capped_row_count_is_a_lower_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("usdata.inspect.ROW_LIMIT", 1)
    fetched = cached(tmp_path, "daily.csv", CSV, media_type="text/csv")
    result = runner.invoke(app, ["inspect", str(fetched.path)])
    assert result.exit_code == 0
    assert "at least 1, scanned the first 1" in result.stdout


def test_the_cli_prints_units_beside_the_columns_that_have_them(tmp_path: Path) -> None:
    cached(tmp_path, "sst.csv", UNITS_CSV, dataset_id="noaa:coastwatch-sst")
    result = runner.invoke(app, ["inspect", str(tmp_path / "sst.csv")])
    assert result.exit_code == 0
    assert "sst (degree_C)" in result.stdout and "time (UTC)" in result.stdout
    rows = next(line for line in result.stdout.splitlines() if "rows:" in line)
    assert rows.split()[-1] == "1"


def test_the_cli_reports_an_empty_csv_as_no_columns(tmp_path: Path) -> None:
    fetched = cached(tmp_path, "empty.csv", b"", media_type="text/csv")
    result = runner.invoke(app, ["inspect", str(fetched.path)])
    assert result.exit_code == 0
    assert "rows:" in result.stdout and "columns: none" in result.stdout


@pytest.mark.netcdf
def test_the_cli_names_the_missing_extra_instead_of_failing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from usdata import _netcdf

    def without_xarray(name: str) -> object:
        raise ModuleNotFoundError(f"No module named {name!r}", name=name)

    monkeypatch.setattr(_netcdf, "import_module", without_xarray)
    fetched = cached(tmp_path, "scene.nc", b"", dataset_id="noaa:goes-abi")
    result = runner.invoke(app, ["inspect", str(fetched.path)])
    assert result.exit_code == 0
    assert "format:" in result.stdout and "netcdf" in result.stdout
    assert "usdata[netcdf]" in result.stdout


@pytest.mark.netcdf
def test_the_cli_prints_the_netcdf_variable_table(tmp_path: Path) -> None:
    pytest.importorskip("h5netcdf")
    pytest.importorskip("h5py")
    pytest.importorskip("xarray")
    fetched = cached(tmp_path, "scene.nc", NETCDF_FIXTURE.read_bytes(), dataset_id="noaa:goes-abi")
    result = runner.invoke(app, ["inspect", str(fetched.path)])
    assert result.exit_code == 0
    assert "variables:" in result.stdout
    assert "name" in result.stdout and "long_name" in result.stdout
    assert "CMI" in result.stdout and "y, x" in result.stdout and "2 x 3" in result.stdout


@pytest.mark.grib
def test_the_cli_prints_the_grib2_message_table(grib: FetchedAsset) -> None:
    result = runner.invoke(app, ["inspect", str(grib.path)])
    assert result.exit_code == 0
    assert "messages:" in result.stdout and "shortName" in result.stdout
    assert "isobaricInhPa" in result.stdout and "3 x 4" in result.stdout
    assert "cape" in result.stdout


@pytest.mark.grib
def test_the_cli_prints_both_numberings_only_for_a_partial_file(
    grib: FetchedAsset, partial_grib: FetchedAsset
) -> None:
    whole = runner.invoke(app, ["inspect", str(grib.path)])
    assert whole.exit_code == 0
    assert "object #" not in whole.stdout and "file #" not in whole.stdout
    part = runner.invoke(app, ["inspect", str(partial_grib.path)])
    assert part.exit_code == 0
    header = next(line for line in part.stdout.splitlines() if "shortName" in line)
    assert header.split()[:5] == ["file", "#", "object", "#", "selector"]
    assert "105" in part.stdout and "131" in part.stdout
    assert "CAPE:surface" in part.stdout and "selector" not in whole.stdout


@pytest.mark.grib
def test_the_cli_says_when_a_grib2_file_holds_no_messages(tmp_path: Path) -> None:
    pytest.importorskip("eccodes")
    pytest.importorskip("numpy")
    pytest.importorskip("xarray")
    fetched = cached(tmp_path, "empty.grib2", b"", dataset_id="noaa:hrrr")
    result = runner.invoke(app, ["inspect", str(fetched.path)])
    assert result.exit_code == 0
    assert "messages: none" in result.stdout


def test_the_cli_exits_2_for_an_unsafe_dataset_id(tmp_path: Path) -> None:
    result = runner.invoke(app, ["inspect", "no aa:x/y", "--cache-dir", str(tmp_path)])
    assert result.exit_code == 2
    assert "unsafe dataset id" in result.output


@pytest.mark.parametrize(
    "target, expected",
    [("noaa:ghcn-daily/absent.csv", "no cached file at"), ("absent.csv", "no file at")],
)
def test_the_cli_exits_2_for_an_unknown_asset(tmp_path: Path, target: str, expected: str) -> None:
    result = runner.invoke(app, ["inspect", target, "--cache-dir", str(tmp_path)])
    assert result.exit_code == 2
    assert expected in result.output


def test_the_cli_exits_2_for_a_file_with_no_sidecar(tmp_path: Path) -> None:
    fetched = cached(tmp_path, "daily.csv", CSV, sidecar=False)
    result = runner.invoke(app, ["inspect", str(fetched.path)])
    assert result.exit_code == 2
    assert "no usable provenance beside" in result.output
