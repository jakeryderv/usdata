from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from usdata.cache import sha256_file
from usdata.fetch import FetchedAsset
from usdata.models import Asset, Protocol, Provenance
from usdata.readers import MissingReaderDependency

pytestmark = pytest.mark.netcdf

FIXTURE = Path(__file__).parents[1] / "fixtures/netcdf/packed-grid.nc"


@pytest.fixture
def item(tmp_path):
    path = tmp_path / "scene.nc"
    path.write_bytes(FIXTURE.read_bytes())
    asset = Asset(
        id="scene.nc",
        dataset_id="noaa:goes-abi",
        href="s3://noaa-goes18/scene.nc",
        protocol=Protocol.S3,
        media_type="application/x-netcdf",
    )
    provenance = Provenance(
        dataset_id=asset.dataset_id,
        provider="noaa",
        source_url=asset.href,
        retrieved_at=datetime(2026, 9, 8, tzinfo=UTC),
        checksum=sha256_file(path),
        size=path.stat().st_size,
        usdata_version="0.7.0",
    )
    return FetchedAsset(asset=asset, path=path, provenance=provenance, from_cache=True)


@pytest.fixture
def xr():
    pytest.importorskip("h5netcdf")
    pytest.importorskip("h5py")
    return pytest.importorskip("xarray")


def test_packed_cf_data_units_coordinates_and_closed_resources(item, xr):
    before = item.path.read_bytes()
    result = item.open()
    assert isinstance(result, xr.Dataset)
    assert dict(result.sizes) == {"y": 2, "x": 3}
    assert result.CMI.attrs["units"] == "K" and result.x.attrs["units"] == "rad"
    assert result.CMI.values[0, 0] == 250 and result.CMI.values[1, 2] == 270
    assert bool(result.CMI.isnull()[0, 2])
    assert result.unsigned_count.values[1] == 32768
    assert bool(result.unsigned_count.isnull()[2])
    assert str(result.t.values).startswith("2024-05-06T12:01:18.100")
    assert result.DQF.values.tolist() == [[0, 1, 3], [0, 0, 0]]
    assert result.attrs["title"] == "Synthetic packed CF test grid"
    assert result.attrs["usdata"]["provenance"] == item.provenance.model_dump(mode="json")
    assert item.path.read_bytes() == before
    assert sha256_file(item.path) == item.provenance.checksum
    # Windows also forbids unlinking an open source: data must be loaded and closed.
    item.path.unlink()
    assert float(result.CMI.mean()) == 260
    result.attrs["usdata"]["provenance"]["checksum"] = "changed locally"
    assert item.provenance.checksum.startswith("sha256:")


@pytest.mark.parametrize("name", ["xarray", "h5netcdf", "h5py"])
def test_missing_dependency_has_actionable_extra(item, name):
    with (
        patch("usdata._netcdf.import_module", side_effect=ModuleNotFoundError(name=name)),
        pytest.raises(MissingReaderDependency, match=r"usdata\[netcdf\]"),
    ):
        item.open()


def test_broken_dependency_not_hidden(item):
    with (
        patch("usdata._netcdf.import_module", side_effect=ModuleNotFoundError(name="unrelated")),
        pytest.raises(ModuleNotFoundError) as error,
    ):
        item.open()
    assert error.value.name == "unrelated"


@pytest.mark.parametrize(
    "options", [{"dtype": {}}, {"parse_dates": []}, {"usecols": []}, {"nrows": 1}]
)
def test_csv_options_rejected_before_loading_dependencies(item, options):
    with patch("usdata._netcdf.import_module") as loader, pytest.raises(ValueError, match="CSV"):
        item.open(**options)
    loader.assert_not_called()


@pytest.mark.parametrize("content", [b"", b"not NetCDF", FIXTURE.read_bytes()[:150]])
def test_invalid_or_truncated_file_fails_without_mutation(item, xr, content):
    item.path.write_bytes(content)
    with pytest.raises((OSError, ValueError)):
        item.open()
    assert item.path.read_bytes() == content
    item.path.unlink()


def test_explicit_reader_on_restored_asset_needs_no_registry(item, xr):
    item.asset = item.asset.model_copy(
        update={"dataset_id": "unknown:archived", "media_type": None}
    )
    with patch("usdata.registry.default_registry", side_effect=AssertionError("no registry")):
        result = item.open(reader="netcdf")
    assert result.CMI.attrs["units"] == "K"


def test_local_file_object_and_fixed_engine(item, xr):
    captured = []
    original = xr.open_dataset

    def capture(source, **kwargs):
        assert not isinstance(source, (str, Path))
        assert kwargs == {"engine": "h5netcdf", "chunks": None}
        captured.append(source)
        return original(source, **kwargs)

    with patch.object(xr, "open_dataset", side_effect=capture):
        item.open()
    assert captured[0].closed


def test_load_failure_still_closes_source(item, xr):
    original = xr.open_dataset
    captured = []

    def capture(source, **kwargs):
        captured.append(source)
        return original(source, **kwargs)

    with (
        patch.object(xr, "open_dataset", side_effect=capture),
        patch.object(xr.Dataset, "load", side_effect=OSError("failed reading array")),
        pytest.raises(OSError, match="failed reading array"),
    ):
        item.open()
    assert captured[0].closed
    item.path.unlink()
