import bz2
import struct
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import respx

from usdata.cache import sha256_file
from usdata.fetch import FetchedAsset
from usdata.models import Asset, Protocol, Provenance
from usdata.readers import MissingReaderDependency, RadarDecodeError

FIXTURES = Path(__file__).parents[1] / "fixtures" / "radar"


def radar_asset(path: Path, dataset: str = "noaa:nexrad-level2") -> FetchedAsset:
    asset = Asset(
        id=path.name,
        dataset_id=dataset,
        href="https://example.test/radar",
        protocol=Protocol.S3,
        media_type="application/octet-stream",
    )
    return FetchedAsset(
        asset=asset,
        path=path,
        provenance=Provenance(
            dataset_id=dataset,
            provider="noaa",
            source_url=asset.href,
            retrieved_at=datetime(2026, 9, 8, tzinfo=UTC),
            checksum=sha256_file(path),
            size=path.stat().st_size,
            usdata_version="0.7.0",
        ),
        from_cache=True,
    )


def test_missing_radar_dependency_and_broken_install() -> None:
    item = radar_asset(FIXTURES / "example_nexrad_archive_msg31_compressed.ar2v")
    with (
        patch("usdata._radar.import_module", side_effect=ModuleNotFoundError(name="xradar")),
        pytest.raises(MissingReaderDependency, match=r"usdata\[radar\]"),
    ):
        item.open()
    with (
        patch("usdata._radar.import_module", side_effect=ModuleNotFoundError(name="numpy")),
        pytest.raises(ModuleNotFoundError) as error,
    ):
        item.open()
    assert error.value.name == "numpy"


@pytest.mark.parametrize("option", ["dtype", "parse_dates", "usecols", "nrows"])
def test_csv_options_rejected_before_import(option) -> None:
    item = radar_asset(FIXTURES / "example_nexrad_archive_msg31_compressed.ar2v")
    with patch("usdata._radar.import_module") as loader, pytest.raises(ValueError, match="CSV"):
        options: dict[str, Any] = {option: 1 if option == "nrows" else []}
        item.open(**options)
    loader.assert_not_called()


@pytest.mark.parametrize(
    "filename,rays,gates,sweeps,minimum,maximum",
    [
        ("example_nexrad_archive_msg1.bz2", 367, 460, 7, -32, 57.5),
        ("example_nexrad_archive_msg31_compressed.ar2v", 720, 1832, 1, -30.5, 44.5),
    ],
)
def test_real_archives_decode_offline(tmp_path, filename, rays, gates, sweeps, minimum, maximum):
    pytest.importorskip("xradar")
    path = tmp_path / filename
    path.write_bytes((FIXTURES / filename).read_bytes())
    item = radar_asset(path)
    item = FetchedAsset.model_validate_json(item.model_dump_json())
    before = path.read_bytes()
    with respx.mock():
        radar = item.open()
    field = radar["sweep_0"]["DBZH"]
    assert field.shape == (rays, gates)
    assert len([g for g in radar.groups if g.startswith("/sweep_")]) == sweeps
    assert field.attrs["units"] == "dBZ"
    if filename.endswith("ar2v"):
        assert int(field.isnull().all(dim="range").sum()) == 600
        assert int(field.count()) == 23363
    assert (field.min().item(), field.max().item()) == (minimum, maximum)
    assert radar.attrs["usdata"]["provenance"]["checksum"] == item.provenance.checksum
    radar.attrs["usdata"]["provenance"]["checksum"] = "changed"
    field.values[:] = 0
    assert item.provenance.checksum == sha256_file(path)
    assert path.read_bytes() == before
    path.unlink()  # the returned arrays do not own an open file handle
    assert field.max().item() == 0


def test_gzip_explicit_reader_and_bad_local_files(tmp_path):
    import gzip

    pytest.importorskip("xradar")
    path = tmp_path / "ambiguous.bin"
    content = (FIXTURES / "example_nexrad_archive_msg31_compressed.ar2v").read_bytes()
    path.write_bytes(gzip.compress(content))
    item = radar_asset(path, "example:ambiguous")
    assert item.open(reader="nexrad-level2")["sweep_0"]["DBZH"].shape == (720, 1832)
    path.write_bytes(b"invalid archive")
    with pytest.raises((ValueError, OSError, EOFError, struct.error)):
        item.open(reader="nexrad-level2")
    path.unlink()
    with pytest.raises(FileNotFoundError):
        item.open(reader="nexrad-level2")


def test_flags_masked_without_changing_valid_moments_or_coordinates():
    xr = pytest.importorskip("xarray")
    pytest.importorskip("xradar")
    ds = xr.Dataset(
        {
            "DBZH": (("azimuth", "range"), [[-33.0, -32.5, -32.0, 0.0]]),
            "CCORH": (("azimuth", "range"), [[-8.0, -1.0, 0.0, 1.0]]),
            "unknown": (("azimuth", "range"), [[0.0, 1.0, 2.0, 3.0]]),
        },
        coords={"azimuth": [0.0], "range": [0.0, 250.0, 500.0, 750.0]},
    )
    ds.DBZH.attrs["units"] = "dBZ"
    ds.DBZH.encoding.update(scale_factor=0.5, add_offset=-33.0, source=b"decoder bytes")
    ds.CCORH.encoding.update(scale_factor=1.0, add_offset=-8.0)
    ds.unknown.encoding.update(scale_factor=1.0, add_offset=0.0)
    tree = xr.DataTree.from_dict({"/sweep_0": ds})
    item = radar_asset(FIXTURES / "example_nexrad_archive_msg31_compressed.ar2v")
    with patch("xradar.io.open_nexradlevel2_datatree", return_value=tree):
        opened = item.open()
    field = opened["sweep_0"]["DBZH"]
    assert field.isnull().values.tolist() == [[True, True, False, False]]
    assert field.values[0, 2:].tolist() == [-32.0, 0.0]
    assert field.attrs["units"] == "dBZ"
    assert field.encoding == {"scale_factor": 0.5, "add_offset": -33.0}
    assert field.azimuth.values.tolist() == [0.0]
    assert field.range.values.tolist() == [0.0, 250.0, 500.0, 750.0]
    assert opened["sweep_0"]["CCORH"].isnull().values.tolist() == [[True, True, False, False]]
    assert opened["sweep_0"]["unknown"].values.tolist() == [[0.0, 1.0, 2.0, 3.0]]


def test_decoder_closed_when_eager_loading_fails() -> None:
    from unittest.mock import Mock

    item = radar_asset(FIXTURES / "example_nexrad_archive_msg31_compressed.ar2v")
    backend = Mock()
    radar = backend.io.open_nexradlevel2_datatree.return_value
    radar.load.side_effect = OSError("decode failed")
    with (
        patch("usdata._radar.import_module", return_value=backend),
        patch("usdata._radar._check_sweeps"),
        pytest.raises(OSError),
    ):
        item.open()
    radar.close.assert_called_once()


@pytest.mark.parametrize("selection", [-1, True, "0", 0.5, [], [0, -1], [False], [0, 0]])
def test_invalid_sweep_selection_before_backend_import(selection: Any):
    item = radar_asset(FIXTURES / "example_nexrad_archive_msg1.bz2")
    with patch("usdata._radar.import_module") as loader, pytest.raises(ValueError, match="sweep"):
        item.open(sweep=selection)
    loader.assert_not_called()


@pytest.mark.parametrize("reader", ["csv", "erddap-csv", "netcdf"])
def test_sweep_rejected_for_other_readers(reader):
    item = radar_asset(FIXTURES / "example_nexrad_archive_msg1.bz2")
    with pytest.raises(ValueError, match="only to the NEXRAD"):
        item.open(reader=reader, sweep=0)


@pytest.mark.parametrize("selection,groups", [(0, ["sweep_0"]), ([0, 2], ["sweep_0", "sweep_2"])])
def test_selected_sweeps_match_full_volume(selection, groups):
    xr = pytest.importorskip("xarray")
    pytest.importorskip("xradar")
    item = radar_asset(FIXTURES / "example_nexrad_archive_msg1.bz2")
    full = item.open()
    selected = item.open(sweep=selection)
    assert selected.attrs["usdata"]["sweeps"] == groups
    assert [g.lstrip("/") for g in selected.groups if g.startswith("/sweep_")] == groups
    for group in groups:
        xr.testing.assert_equal(full[group].to_dataset(), selected[group].to_dataset())
    with pytest.raises(ValueError, match="outside this volume"):
        item.open(sweep=7)


def test_missing_interior_end_marker_rejects_shifted_coordinates(tmp_path):
    backend = pytest.importorskip("xradar.io.backends.nexrad_level2")
    # Reproduce the KTLX 2024-05-07 04:40:53 structural defect on the small
    # legacy fixture: change only sweep 1's final radial status from end (2)
    # to intermediate (1). Moment bytes are untouched. This is deliberately
    # damaged test data, not another archived scientific observation.
    raw = bytearray(bz2.decompress((FIXTURES / "example_nexrad_archive_msg1.bz2").read_bytes()))
    with backend.NEXRADLevel2File(bytes(raw), loaddata=False) as volume:
        _ = volume.incomplete_sweeps
        # Record prefix 12 bytes + message header 16 + MSG_1 status offset 12.
        offset = volume.msg_31_header[1][-1]["filepos"] + 12 + 16 + 12
    assert struct.unpack_from(">H", raw, offset) == (2,)
    struct.pack_into(">H", raw, offset, 1)
    path = tmp_path / "missing-interior-end.ar2v"
    path.write_bytes(raw)
    item = radar_asset(path)
    checksum = item.provenance.checksum
    for selection in [None, 1, 2, 4, 6, [0, 4]]:
        with pytest.raises(RadarDecodeError, match="No sweeps were silently dropped"):
            item.open(sweep=selection)
    # Sweep 4 has the same ray count as the wrongly paired sweep 5: a shape
    # check alone cannot catch this loss of coordinate/timestamp alignment.
    with backend.NEXRADLevel2File(bytes(raw), loaddata=False) as volume:
        _ = volume.incomplete_sweeps
        assert len(volume.msg_31_header[4]) == 366
        assert volume.data[4]["record_end"] - volume.data[4]["record_number"] + 1 == 366
        assert volume.msg_31_header[4][0]["record_number"] != volume.data[4]["record_number"]
    selected = item.open(sweep=0)
    assert selected["sweep_0"].DBZH.shape == (367, 460)
    assert selected.attrs["usdata"]["sweeps"] == ["sweep_0"]
    assert selected.attrs["usdata"]["provenance"]["checksum"] == checksum == sha256_file(path)


def test_incomplete_sweep_with_trailing_non_radial_record(tmp_path):
    xr = pytest.importorskip("xarray")
    xradar = pytest.importorskip("xradar")
    backend = pytest.importorskip("xradar.io.backends.nexrad_level2")

    raw = bytearray(bz2.decompress((FIXTURES / "example_nexrad_archive_msg1.bz2").read_bytes()))
    with backend.NEXRADLevel2File(bytes(raw), loaddata=False) as volume:
        _ = volume.incomplete_sweeps
        last_record = volume.msg_31_header[0][170]["filepos"]
        stop = volume.msg_31_header[0][171]["filepos"]
    raw = raw[:stop]
    # Change the last received record's message type to non-radial (2).
    # The partial sweep now ends with metadata, not its last coordinate ray.
    assert raw[last_record + 12 + 3] == 1
    raw[last_record + 12 + 3] = 2
    path = tmp_path / "trailing-metadata.ar2v"
    path.write_bytes(raw)
    native = xradar.io.open_nexradlevel2_datatree(bytes(raw), sweep=0, incomplete_sweep="pad")
    try:
        native.load()
    finally:
        native.close()
    opened = radar_asset(path).open(sweep=0)
    assert opened["sweep_0"].DBZH.shape == native["sweep_0"].DBZH.shape
    # The SDK masks reserved moment flags; coordinates and valid samples agree.
    xr.testing.assert_equal(opened["sweep_0"].time, native["sweep_0"].time)
    xr.testing.assert_equal(opened["sweep_0"].azimuth, native["sweep_0"].azimuth)
    xr.testing.assert_equal(
        opened["sweep_0"].DBZH, native["sweep_0"].DBZH.where(native["sweep_0"].DBZH >= -32)
    )
