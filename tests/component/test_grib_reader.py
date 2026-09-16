"""GRIB2 reader: synthetic ecCodes messages, selection, grids, gzip, and resource closure."""

from __future__ import annotations

import gzip
import os
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from usdata import FetchedAsset
from usdata.cache import sha256_file
from usdata.models import Asset, ByteRange, Protocol, Provenance
from usdata.readers import MissingReaderDependency, open_asset

pytestmark = [pytest.mark.l2, pytest.mark.grib]

ec = pytest.importorskip("eccodes")
np = pytest.importorskip("numpy")
xr = pytest.importorskip("xarray")

REGULAR = {
    "Ni": 4,
    "Nj": 3,
    "latitudeOfFirstGridPointInDegrees": 40.0,
    "longitudeOfFirstGridPointInDegrees": 250.0,
    "latitudeOfLastGridPointInDegrees": 38.0,
    "longitudeOfLastGridPointInDegrees": 253.0,
    "iDirectionIncrementInDegrees": 1.0,
    "jDirectionIncrementInDegrees": 1.0,
}
LAMBERT = {
    "gridType": "lambert",
    "Nx": 3,
    "Ny": 2,
    "LaDInDegrees": 38.5,
    "LoVInDegrees": 262.5,
    "Latin1InDegrees": 38.5,
    "Latin2InDegrees": 38.5,
    "latitudeOfFirstGridPointInDegrees": 21.1,
    "longitudeOfFirstGridPointInDegrees": 237.3,
    "DxInMetres": 3000.0,
    "DyInMetres": 3000.0,
    "shapeOfTheEarth": 6,
}


def message(values, *, grid=REGULAR, param=130, level_type="surface", level=0, **keys) -> bytes:
    """One GRIB2 message from the ecCodes regular_ll sample, simple packing."""
    handle = ec.codes_grib_new_from_samples("regular_ll_sfc_grib2")
    try:
        for key, value in grid.items():
            ec.codes_set(handle, key, value)
        # ecCodes resolves paramId against the level already set; explicit keys come last.
        ec.codes_set(handle, "typeOfLevel", level_type)
        ec.codes_set(handle, "level", level)
        ec.codes_set(handle, "paramId", param)
        for key, value in keys.items():
            ec.codes_set(handle, key, value)
        ec.codes_set(handle, "packingType", "grid_simple")
        ec.codes_set(handle, "dataDate", 20240506)
        ec.codes_set(handle, "dataTime", 2000)
        ec.codes_set_values(handle, np.asarray(values, dtype=float).ravel())
        return ec.codes_get_message(handle)
    finally:
        ec.codes_release(handle)


def message_ranges(content: bytes) -> list[ByteRange]:
    """One inclusive byte range per message, as a partial fetch records them."""
    ranges: list[ByteRange] = []
    offset = 0
    while offset < len(content):
        length = int.from_bytes(content[offset + 8 : offset + 16], "big")
        ranges.append(ByteRange(start=offset, end=offset + length - 1))
        offset += length
    return ranges


def item(
    tmp_path: Path,
    content: bytes,
    name="field.grib2",
    media_type="application/x-grib2",
    dataset_id="noaa:hrrr",
    messages: list[int] | None = None,
):
    path = tmp_path / name
    path.write_bytes(content)
    href = f"s3://noaa-hrrr-bdp-pds/{name}"
    partial: dict[str, Any] = {}
    if messages is not None:
        # What a partial fetch records: the object, its index, and the ranges it read.
        numbers = ",".join(str(number) for number in messages)
        href = f"{href}#messages={numbers}"
        partial = {
            "transformations": [
                f"grib2 messages {numbers} concatenated from s3://noaa-hrrr-bdp-pds/{name}"
            ],
            "index_url": f"s3://noaa-hrrr-bdp-pds/{name}.idx",
            "index_checksum": "sha256:" + "0" * 64,
            "ranges": message_ranges(content),
            "object_size": path.stat().st_size,
            "object_etag": "81198a73ad430c73adfbe3335421ea99",
        }
    asset = Asset(
        id=name,
        dataset_id=dataset_id,
        href=href,
        protocol=Protocol.S3,
        media_type=media_type,
    )
    provenance = Provenance(
        dataset_id=asset.dataset_id,
        provider="noaa",
        source_url=asset.href,
        retrieved_at=datetime(2026, 9, 14, tzinfo=UTC),
        checksum=sha256_file(path),
        size=path.stat().st_size,
        usdata_version="0.15.0",
        **partial,
    )
    return FetchedAsset(asset=asset, path=path, provenance=provenance, from_cache=True)


def open_fds() -> set[str] | None:
    try:
        return set(os.listdir("/proc/self/fd"))
    except OSError:
        return None


def test_regular_grid_coordinates_values_attrs_and_provenance(tmp_path) -> None:
    values = np.arange(12, dtype=float).reshape(3, 4)
    fetched = item(tmp_path, message(values))
    before = fetched.path.read_bytes()
    fds = open_fds()
    result = fetched.open()
    assert isinstance(result, xr.Dataset)
    assert fetched.path.read_bytes() == before
    assert fds is None or open_fds() == fds
    assert list(result.data_vars) == ["t"]
    assert result.t.dims == ("latitude", "longitude") and result.t.dtype == np.float32
    assert result.latitude.values.tolist() == [40.0, 39.0, 38.0]
    assert result.longitude.values.tolist() == [250.0, 251.0, 252.0, 253.0]
    assert result.t.values.tolist() == values.tolist()
    assert result.t.attrs["units"] == "K" and result.t.attrs["name"] == "Temperature"
    assert result.t.attrs["typeOfLevel"] == "surface" and result.t.attrs["level"] == 0
    assert result.t.attrs["packingType"] == "grid_simple"
    assert result.t.attrs["reference_time"] == "2024-05-06T20:00:00+00:00"
    assert result.t.attrs["valid_time"] == "2024-05-06T20:00:00+00:00"
    assert (result.t.attrs["discipline"], result.t.attrs["parameterCategory"]) == (0, 0)
    assert result.attrs["gridType"] == "regular_ll"
    assert result.latitude.attrs["units"] == "degrees_north"
    assert result.attrs["usdata"] == {
        "asset_id": "field.grib2",
        "provenance": fetched.provenance.model_dump(mode="json"),
        "messages": {
            "t": {
                "file_index": 0,
                "object_index": None,
                "shortName": "t",
                "typeOfLevel": "surface",
                "level": 0,
                "step": 0,
            }
        },
    }


def test_bitmap_missing_values_become_nan(tmp_path) -> None:
    values = np.arange(12, dtype=float)
    values[5] = 9999
    content = message(values, missingValue=9999, bitmapPresent=1)
    result = item(tmp_path, content).open()
    grid = result.t.values
    assert np.isnan(grid[1, 1]) and np.isnan(grid).sum() == 1
    assert grid[2, 3] == 11


def test_gzip_and_plain_files_decode_identically(tmp_path) -> None:
    content = message(np.arange(12, dtype=float))
    plain = item(tmp_path, content).open()
    zipped = item(
        tmp_path, gzip.compress(content), name="field.grib2.gz", media_type="application/gzip"
    )
    before = zipped.path.read_bytes()
    result = zipped.open()
    assert zipped.path.read_bytes() == before
    del plain.attrs["usdata"], result.attrs["usdata"]
    xr.testing.assert_identical(plain, result)


def test_south_to_north_scanning_is_reordered_north_to_south(tmp_path) -> None:
    values = np.arange(12, dtype=float).reshape(3, 4)
    content = message(
        values,
        jScansPositively=1,
        latitudeOfFirstGridPointInDegrees=38.0,
        latitudeOfLastGridPointInDegrees=40.0,
    )
    result = item(tmp_path, content).open()
    assert result.latitude.values.tolist() == [40.0, 39.0, 38.0]
    assert result.t.values.tolist() == values[::-1].tolist()


def test_lambert_grid_has_two_dimensional_coordinates_and_projection(tmp_path) -> None:
    content = message(np.arange(6, dtype=float), grid=LAMBERT, param=59)
    result = item(tmp_path, content).open()
    assert list(result.data_vars) == ["cape"]
    assert result.cape.dims == ("y", "x") and result.cape.shape == (2, 3)
    assert result.latitude.dims == ("y", "x") and result.longitude.dims == ("y", "x")
    assert result.latitude.values[0, 0] == pytest.approx(21.1, abs=1e-6)
    assert result.longitude.values[0, 0] == pytest.approx(237.3, abs=1e-6)
    assert result.attrs["gridType"] == "lambert"
    assert result.attrs["LoVInDegrees"] == 262.5 and result.attrs["DxInMetres"] == 3000.0
    assert result.attrs["shapeOfTheEarth"] == 6
    assert result.cape.attrs["units"] == "J kg**-1"


@pytest.fixture
def levels(tmp_path):
    """Two short names at 500 hPa and one of them again at 850, all on one grid."""
    parts = [
        message(np.full(12, 500.0), level_type="isobaricInhPa", level=500),
        message(np.full(12, 55.0), param=157, level_type="isobaricInhPa", level=500),
        message(np.full(12, 850.0), level_type="isobaricInhPa", level=850),
    ]
    return item(tmp_path, b"".join(parts), name="levels.grib2")


@pytest.fixture
def multi(tmp_path):
    parts = [
        message(np.full(12, 500.0), level_type="isobaricInhPa", level=500),
        message(np.full(12, 850.0), level_type="isobaricInhPa", level=850),
        message(np.full(12, 7.0), param=59, level_type="surface", level=0),
    ]
    return item(tmp_path, b"".join(parts), name="multi.grib2")


def test_multi_message_file_requires_select_and_lists_messages(multi) -> None:
    with pytest.raises(ValueError, match=r"3 messages; pass select") as error:
        multi.open()
    assert "('t', 'isobaricInhPa', '500')" in str(error.value)
    assert "('cape', 'entireAtmosphere', '0')" in str(error.value)


def test_select_by_value_and_list_and_numeric_level(multi) -> None:
    both = multi.open(select={"shortName": "t", "level": [500, 850]})
    assert set(both.data_vars) == {"t_isobaricInhPa_500", "t_isobaricInhPa_850"}
    assert float(both["t_isobaricInhPa_850"].values[0, 0]) == 850.0
    one = multi.open(select={"shortName": "t", "level": 500})
    assert list(one.data_vars) == ["t"] and one.t.attrs["level"] == 500
    text = multi.open(select={"level": "850"})
    assert list(text.data_vars) == ["t"]
    surface = multi.open(select={"shortName": "cape", "typeOfLevel": "entireAtmosphere"})
    assert list(surface.data_vars) == ["cape"]


def test_one_level_keeps_bare_names_and_more_levels_suffix_every_variable(levels) -> None:
    one = levels.open(select={"level": 500})
    assert set(one.data_vars) == {"t", "r"}
    spanning = levels.open(select={"shortName": ["t", "r"], "level": [500, 850]})
    # 'r' occurs once and is suffixed anyway: the names follow the select, not the collisions.
    assert set(spanning.data_vars) == {
        "t_isobaricInhPa_500",
        "r_isobaricInhPa_500",
        "t_isobaricInhPa_850",
    }


def test_more_than_one_level_type_suffixes_distinct_short_names_too(multi) -> None:
    result = multi.open(select={"shortName": ["t", "cape"], "level": [500, 0]})
    assert set(result.data_vars) == {"t_isobaricInhPa_500", "cape_entireAtmosphere_0"}


def test_messages_attribute_maps_every_variable_to_the_message_it_came_from(levels) -> None:
    result = levels.open(select={"shortName": ["t", "r"], "level": [500, 850]})
    assert result.attrs["usdata"]["messages"] == {
        "t_isobaricInhPa_500": {
            "file_index": 0,
            "object_index": None,
            "shortName": "t",
            "typeOfLevel": "isobaricInhPa",
            "level": 500,
            "step": 0,
        },
        "r_isobaricInhPa_500": {
            "file_index": 1,
            "object_index": None,
            "shortName": "r",
            "typeOfLevel": "isobaricInhPa",
            "level": 500,
            "step": 0,
        },
        "t_isobaricInhPa_850": {
            "file_index": 2,
            "object_index": None,
            "shortName": "t",
            "typeOfLevel": "isobaricInhPa",
            "level": 850,
            "step": 0,
        },
    }
    # file_index numbers every message in the file, not just the selected ones.
    bare = levels.open(select={"level": 850})
    assert bare.attrs["usdata"]["messages"]["t"]["file_index"] == 2


def test_select_without_match_or_with_bad_values_is_rejected(multi) -> None:
    with pytest.raises(ValueError, match=r"matched no messages.*'cape'"):
        multi.open(select={"shortName": "nope"})
    with pytest.raises(ValueError, match="must not be empty"):
        multi.open(select={"shortName": []})
    with pytest.raises(ValueError, match="strings or numbers"):
        multi.open(select={"level": [True]})
    with pytest.raises(ValueError, match="mapping"):
        multi.open(select=["shortName"])  # type: ignore[arg-type]


def test_unmatched_select_value_warns_and_names_what_was_available(multi) -> None:
    select = {"shortName": ["t", "nope"], "level": 500}
    with pytest.warns(UserWarning) as record:
        result = multi.open(select=select)
    assert list(result.data_vars) == ["t"]
    assert len(record) == 1
    text = str(record[0].message)
    assert "select['shortName'] matched no message for 'nope'" in text
    assert "shortName values available with the other select keys: 't'" in text
    # The warning names the caller, not a usdata frame, through either entry point.
    assert Path(record[0].filename).resolve() == Path(__file__).resolve()
    with pytest.warns(UserWarning) as direct:
        open_asset(multi, select=select)
    assert Path(direct[0].filename).resolve() == Path(__file__).resolve()


def test_strict_raises_for_an_unmatched_value_and_keeps_the_no_match_error(multi) -> None:
    with pytest.raises(ValueError, match=r"select\['shortName'\] matched no message for 'nope'"):
        multi.open(select={"shortName": ["t", "nope"], "level": 500}, strict=True)
    with pytest.raises(ValueError, match=r"matched no messages.*'cape'"):
        multi.open(select={"shortName": "nope"}, strict=True)


def test_fully_matched_select_neither_warns_nor_raises(multi) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = multi.open(select={"shortName": ["t", "cape"], "level": [500, 0]}, strict=True)
    assert set(result.data_vars) == {"t_isobaricInhPa_500", "cape_entireAtmosphere_0"}


def test_mrms_products_are_named_from_the_asset_when_eccodes_has_no_name(tmp_path) -> None:
    content = message(
        np.arange(12, dtype=float), discipline=209, parameterCategory=3, parameterNumber=14
    )
    name = "MRMS_RotationTrackML30min_00.50_20240506-200000.grib2.gz"
    fetched = item(tmp_path, gzip.compress(content), name=name, media_type="application/gzip")
    result = fetched.open()
    assert list(result.data_vars) == ["RotationTrackML30min"]
    assert result.RotationTrackML30min.attrs["parameterNumber"] == 14
    other = item(tmp_path, content, name="local.grib2", media_type="application/octet-stream")
    assert list(other.open().data_vars) == ["parameter_209_3_14"]


def test_registry_fills_units_and_long_name_the_file_leaves_unknown(tmp_path) -> None:
    content = message(
        np.arange(12, dtype=float), discipline=209, parameterCategory=3, parameterNumber=14
    )
    name = "MRMS_RotationTrackML30min_00.50_20240506-200000.grib2"
    result = item(tmp_path, content, name=name, dataset_id="noaa:mrms").open()
    # The decoded name drops the level suffix the registry entry's name carries.
    track = result.RotationTrackML30min
    assert track.attrs["units"] == "0.001 s-1"
    assert track.attrs["long_name"] == "30-minute maximum mid-level azimuthal shear"
    assert result.attrs["usdata"]["registry_attrs"] == [
        {"variable": "RotationTrackML30min", "attribute": "units"},
        {"variable": "RotationTrackML30min", "attribute": "long_name"},
    ]


def test_registry_never_overwrites_units_the_file_provides(tmp_path) -> None:
    content = message(np.arange(6, dtype=float), grid=LAMBERT, param=59)
    result = item(tmp_path, content).open()
    assert result.cape.attrs["units"] == "J kg**-1"
    assert result.cape.attrs["long_name"] == (
        "Convective available potential energy, surface or a ground layer"
    )
    assert result.attrs["usdata"]["registry_attrs"] == [
        {"variable": "cape", "attribute": "long_name"}
    ]


def test_registry_leaves_a_dataset_without_an_entry_alone(tmp_path) -> None:
    fetched = item(tmp_path, message(np.arange(12, dtype=float)))
    fetched.asset = fetched.asset.model_copy(update={"dataset_id": "unknown:archived"})
    result = fetched.open()
    assert result.t.attrs["units"] == "K" and "long_name" not in result.t.attrs
    assert "registry_attrs" not in result.attrs["usdata"]


def test_reader_options_are_scoped(tmp_path) -> None:
    fetched = item(tmp_path, message(np.arange(12, dtype=float)))
    with pytest.raises(ValueError, match="CSV options"):
        fetched.open(nrows=1)
    with pytest.raises(ValueError, match="sweep applies only"):
        fetched.open(sweep=0)
    assert isinstance(fetched.open(reader="grib2"), xr.Dataset)
    csv_item = item(tmp_path, b"a,b\n1,2\n", name="table.csv", media_type="text/csv")
    with pytest.raises(ValueError, match="select applies only"):
        csv_item.open(select={"shortName": "t"})
    with pytest.raises(ValueError, match="strict applies only"):
        csv_item.open(strict=True)


def test_grib1_and_truncated_messages_are_rejected(tmp_path) -> None:
    content = message(np.arange(12, dtype=float))
    old = bytearray(content)
    old[7] = 1
    with pytest.raises(ValueError, match="edition 2"):
        item(tmp_path, gzip.compress(bytes(old)), name="old.grib2.gz").open()
    with pytest.raises(ValueError, match="truncated"):
        item(tmp_path, gzip.compress(content[:40]), name="cut.grib2.gz").open()
    with pytest.raises(ValueError, match="not a GRIB message"):
        item(tmp_path, gzip.compress(b"NOPE" + content[4:]), name="bad.grib2.gz").open()


def test_missing_dependency_and_missing_library_messages(tmp_path) -> None:
    fetched = item(tmp_path, message(np.arange(12, dtype=float)))
    with (
        patch("usdata._grib.import_module", side_effect=ModuleNotFoundError(name="eccodes")),
        pytest.raises(MissingReaderDependency, match=r"usdata\[grib\]"),
    ):
        open_asset(fetched)
    with (
        patch(
            "usdata._grib.import_module",
            side_effect=RuntimeError("Cannot find the ecCodes library"),
        ),
        pytest.raises(MissingReaderDependency, match="conda-forge"),
    ):
        open_asset(fetched)


def test_a_partial_fetch_opens_with_and_without_select(tmp_path) -> None:
    """A concatenation of chosen messages needs no select: the fetch already chose."""
    parts = [
        message(np.full(12, 288.0), level_type="heightAboveGround", level=2),
        message(np.full(12, 1500.0), param=59, level_type="surface", level=0),
    ]
    fetched = item(tmp_path, b"".join(parts), name="part.grib2", messages=[71, 170])
    assert fetched.provenance.is_partial
    everything = fetched.open()
    # Two level types, so the same rule a select would follow suffixes both variables.
    assert set(everything.data_vars) == {"2t_heightAboveGround_2", "cape_entireAtmosphere_0"}
    assert float(everything["2t_heightAboveGround_2"].values[0, 0]) == 288.0
    assert everything.attrs["usdata"]["messages"]["cape_entireAtmosphere_0"] == {
        "file_index": 1,
        "object_index": 170,
        "shortName": "cape",
        "typeOfLevel": "entireAtmosphere",
        "level": 0,
        "step": 0,
    }
    one = fetched.open(select={"shortName": "cape"})
    assert list(one.data_vars) == ["cape"]
    # One recorded range per selected message, which is what pairs the two numberings.
    assert one.attrs["usdata"]["provenance"]["ranges"] == [
        {"start": 0, "end": len(parts[0]) - 1},
        {"start": len(parts[0]), "end": fetched.path.stat().st_size - 1},
    ]
    assert one.attrs["usdata"]["messages"]["cape"]["object_index"] == 170


def test_a_partial_fetch_of_one_level_keeps_bare_names(tmp_path) -> None:
    parts = [
        message(np.full(12, 500.0), level_type="isobaricInhPa", level=500),
        message(np.full(12, 55.0), param=157, level_type="isobaricInhPa", level=500),
    ]
    fetched = item(tmp_path, b"".join(parts), name="level.grib2", messages=[12, 13])
    assert set(fetched.open().data_vars) == {"t", "r"}


def test_a_whole_file_of_the_same_bytes_still_demands_select(tmp_path) -> None:
    parts = [
        message(np.full(12, 288.0), level_type="heightAboveGround", level=2),
        message(np.full(12, 1500.0), param=59, level_type="surface", level=0),
    ]
    whole = item(tmp_path, b"".join(parts), name="whole.grib2")
    with pytest.raises(ValueError, match=r"2 messages; pass select"):
        whole.open()
