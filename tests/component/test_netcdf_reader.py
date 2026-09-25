from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from usdata import FetchedAsset
from usdata.cache import sha256_file
from usdata.models import Asset, Dataset, Protocol, Provenance, Status, Variable
from usdata.readers import MissingReaderDependency, fill_registry_attrs
from usdata.registry import Registry

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


@pytest.mark.parametrize("content", [b"", b"not NetCDF", FIXTURE.read_bytes()[:150]])
def test_invalid_or_truncated_file_fails_without_mutation(item, xr, content):
    item.path.write_bytes(content)
    with pytest.raises((OSError, ValueError)):
        item.open()
    assert item.path.read_bytes() == content
    item.path.unlink()


def test_explicit_reader_on_restored_asset_needs_no_registry_entry(item, xr):
    item.asset = item.asset.model_copy(
        update={"dataset_id": "unknown:archived", "media_type": None}
    )
    result = item.open_netcdf()
    assert result.CMI.attrs["units"] == "K"
    assert "registry_attrs" not in result.attrs["usdata"]


def synthetic(*variables: Variable) -> Registry:
    """A one-entry registry standing in for the bundled one, so the fixture stays independent."""
    entry = Dataset(
        id="noaa:goes-abi",
        provider="noaa",
        title="Synthetic entry",
        protocol=Protocol.S3,
        domain="weather-satellites",
        status=Status.AVAILABLE,
        since="0.15",
        summary="Synthetic entry",
        formats=["NetCDF4"],
        adapter="usdata.providers.noaa.goes:GoesAbi",
        variables=list(variables),
    )
    return Registry([entry])


def test_registry_variables_fill_only_what_the_file_leaves_unstated(item, xr):
    registry = synthetic(
        Variable(name="cmi", units="reflectance factor", description="Cloud and moisture imagery"),
        Variable(name="DQF", units="%", description="Per-pixel data quality flags"),
        Variable(name="t", units="CF datetime", description="Scene mid-point time"),
    )
    with patch("usdata.registry.default_registry", return_value=registry):
        result = item.open()
    # The file states both for CMI, which a case-insensitive match must not overwrite.
    assert result.CMI.attrs["units"] == "K"
    assert result.CMI.attrs["long_name"] == "Packed brightness temperature"
    assert result.DQF.attrs["units"] == "1"
    assert result.DQF.attrs["long_name"] == "Per-pixel data quality flags"
    # The file states t's units, which decoding moved into its encoding.
    assert "units" not in result.t.attrs
    assert result.t.encoding["units"].startswith("seconds since 2024-05-06")
    assert result.t.attrs["long_name"] == "Scene mid-point time"
    assert result.unsigned_count.attrs == {"units": "1"}
    assert result.attrs["usdata"]["registry_attrs"] == [
        {"variable": "DQF", "attribute": "long_name"},
        {"variable": "t", "attribute": "long_name"},
    ]


def glm_file(xr, path: Path) -> None:
    """A GLM-shaped file: flash times stored as CF offsets, a duration, and a unit-less field."""
    numpy = pytest.importorskip("numpy")
    offsets = numpy.array([-0.2, -0.1], dtype="float32")
    epoch = {"units": "seconds since 2024-05-06 20:00:00.000"}
    xr.Dataset(
        {
            "flash_time_offset_of_first_event": ("number_of_flashes", offsets, epoch),
            "flash_time_offset_of_last_event": ("number_of_flashes", offsets + 0.05, epoch),
            "flash_duration": ("number_of_flashes", offsets + 0.3, {"units": "seconds"}),
            "flash_area": ("number_of_flashes", numpy.array([4.0e8, 2.0e8], dtype="float32")),
        }
    ).to_netcdf(path, engine="h5netcdf")


def test_decoded_time_variables_gain_no_registry_units_and_write_back(item, xr, tmp_path):
    """Registry units on a decoded time variable made ``to_netcdf`` refuse to write it."""
    glm_file(xr, item.path)
    registry = synthetic(
        Variable(name="flash_time_offset_of_first_event", units="CF datetime", description="First"),
        Variable(name="flash_time_offset_of_last_event", units="CF datetime", description="Last"),
        Variable(name="flash_duration", units="s", description="Duration"),
        Variable(name="flash_area", units="m2", description="Area"),
    )
    with patch("usdata.registry.default_registry", return_value=registry):
        result = item.open_netcdf()
    for name in ("flash_time_offset_of_first_event", "flash_time_offset_of_last_event"):
        assert result[name].dtype.kind == "M"
        assert "units" not in result[name].attrs
    assert result.flash_duration.attrs["units"] == "seconds"
    # A variable the file leaves unit-less, and that is not a time, is still filled.
    assert result.flash_area.attrs["units"] == "m2"
    filled = result.attrs["usdata"]["registry_attrs"]
    assert [entry for entry in filled if entry["attribute"] == "units"] == [
        {"variable": "flash_area", "attribute": "units"}
    ]
    del result.attrs["usdata"]
    written = tmp_path / "round-trip.nc"
    result.to_netcdf(written, engine="h5netcdf")
    with xr.open_dataset(written, engine="h5netcdf") as back:
        assert back.flash_time_offset_of_first_event.equals(result.flash_time_offset_of_first_event)


def test_datetime_and_timedelta_variables_never_gain_registry_units(item, xr):
    """Even with no encoding to say so, xarray owns a time variable's units."""
    numpy = pytest.importorskip("numpy")
    data = xr.Dataset(
        {
            "t": ("n", numpy.array(["2024-05-06T20:00"], dtype="datetime64[ns]")),
            "flash_duration": ("n", numpy.array([300], dtype="timedelta64[ms]")),
        },
        attrs={"usdata": {}},
    )
    registry = synthetic(
        Variable(name="t", units="CF datetime", description="Time"),
        Variable(name="flash_duration", units="s", description="Duration"),
    )
    with patch("usdata.registry.default_registry", return_value=registry):
        fill_registry_attrs(item, data)
    assert "units" not in data.t.attrs and "units" not in data.flash_duration.attrs
    assert data.flash_duration.attrs["long_name"] == "Duration"


def test_registry_entry_without_variables_records_nothing(item, xr):
    with patch("usdata.registry.default_registry", return_value=synthetic()):
        result = item.open()
    assert result.CMI.attrs["units"] == "K"
    assert "long_name" not in result.DQF.attrs
    assert "registry_attrs" not in result.attrs["usdata"]


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
