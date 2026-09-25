import warnings
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from usdata import FetchedAsset, build_query, fetch, get
from usdata.models import Asset, Protocol, Provenance
from usdata.readers import MissingReaderDependency, UnsupportedFormat

pytestmark = pytest.mark.pandas


@pytest.fixture
def pd():
    return pytest.importorskip("pandas")


@pytest.fixture
def fetched(tmp_path):
    def make(content, *, protocol=Protocol.HTTP, media_type="text/csv", dataset="noaa:ghcn-daily"):
        path = tmp_path / "sample.csv"
        path.write_text(content, encoding="utf-8")
        asset = Asset(
            id="sample.csv",
            dataset_id=dataset,
            href="https://example.test/sample.csv",
            protocol=protocol,
            media_type=media_type,
        )
        from usdata.cache import sha256_file

        provenance = Provenance(
            dataset_id=dataset,
            provider=dataset.split(":")[0],
            source_url=asset.href,
            retrieved_at=datetime(2026, 9, 5, tzinfo=UTC),
            checksum=sha256_file(path),
            size=path.stat().st_size,
            usdata_version="0.5.0",
        )
        return FetchedAsset(asset=asset, path=path, provenance=provenance, from_cache=True)

    return make


def test_missing_pandas_names_the_extra(fetched) -> None:
    item = fetched("STATION,TMAX\n00123,25\n")
    with (
        patch("usdata.readers.import_module", side_effect=ModuleNotFoundError(name="pandas")),
        pytest.raises(MissingReaderDependency, match=r"usdata\[pandas\]"),
    ):
        item.open()


def test_missing_pandas_names_the_extra_for_hurdat2(fetched) -> None:
    item = fetched("AL011851, UNNAMED, 0,\n", media_type="text/plain", dataset="noaa:hurdat2")
    with (
        patch("usdata._hurdat2.import_module", side_effect=ModuleNotFoundError(name="pandas")),
        pytest.raises(MissingReaderDependency, match=r"usdata\[pandas\]"),
    ):
        item.open()


def test_broken_hurdat2_dependency_is_not_misreported(fetched) -> None:
    item = fetched("AL011851, UNNAMED, 0,\n", media_type="text/plain", dataset="noaa:hurdat2")
    with (
        patch("usdata._hurdat2.import_module", side_effect=ModuleNotFoundError(name="numpy")),
        pytest.raises(ModuleNotFoundError) as error,
    ):
        item.open()
    assert error.value.name == "numpy"


def test_broken_pandas_dependency_is_not_misreported(fetched) -> None:
    item = fetched("STATION,TMAX\n00123,25\n")
    with (
        patch("usdata.readers.import_module", side_effect=ModuleNotFoundError(name="numpy")),
        pytest.raises(ModuleNotFoundError) as error,
    ):
        item.open()
    assert error.value.name == "numpy"


@pytest.mark.parametrize("media_type", [None, "application/octet-stream", "application/x-hdf"])
def test_unsupported_formats_do_not_load_pandas(fetched, media_type) -> None:
    item = fetched("not CSV", media_type=media_type)
    with (
        patch("usdata.readers.import_module") as loader,
        pytest.raises(UnsupportedFormat, match=r"fetched\.path"),
    ):
        item.open()
    loader.assert_not_called()


def test_level3_products_are_refused_without_the_level2_reader(fetched) -> None:
    item = fetched("SDUS54", media_type="application/octet-stream", dataset="noaa:nexrad-level3")
    with (
        patch("usdata.readers.import_module") as loader,
        patch("usdata._radar.open_nexrad", create=True) as radar,
        pytest.raises(UnsupportedFormat, match=r"fetched\.path.*Py-ART"),
    ):
        item.open()
    loader.assert_not_called()
    radar.assert_not_called()


@pytest.mark.parametrize(
    ("media_type", "name"),
    [
        ("application/x-grib2", "sample.csv"),
        ("application/octet-stream", "MRMS_MESH_00.50_20240506-200036.grib2.gz"),
        ("application/gzip", "field.grib2.gz"),
        (None, "hrrr.t20z.wrfsfcf00.grib2"),
    ],
)
def test_grib2_is_inferred_and_names_the_grib_extra(fetched, media_type, name) -> None:
    item = fetched("not GRIB", media_type=media_type)
    item = item.model_copy(update={"asset": item.asset.model_copy(update={"id": name})})
    with (
        patch("usdata._grib.import_module", side_effect=ModuleNotFoundError(name="eccodes")),
        pytest.raises(MissingReaderDependency, match=r"usdata\[grib\]"),
    ):
        item.open()


def test_level_iii_has_no_reader_by_inference_or_by_name(fetched) -> None:
    item = fetched("not a product", media_type=None, dataset="noaa:nexrad-level3")
    for opener in (item.open, item.open_nexrad):
        with pytest.raises(UnsupportedFormat, match="Level III products have no usdata reader"):
            opener()


def test_request_properties_reach_the_frame_by_either_open(pd, fetched) -> None:
    item = fetched("DATE,PRCP\n2024-05-06,10.9\n")
    assert item.open().attrs["usdata"]["properties"] == {}
    stated = item.model_copy(
        update={"asset": item.asset.model_copy(update={"properties": {"units": "metric"}})}
    )
    for frame in (stated.open(), stated.open_csv()):
        assert frame.attrs["usdata"]["properties"] == {"units": "metric"}
        assert "units" not in frame.attrs  # units the file states, per column, stay separate


def test_csv_identifiers_dates_and_numeric_observations(pd, fetched) -> None:
    item = fetched(
        'STATION,DATE,TMAX,NAME\n00123,2024-05-06,25.5,"Norman, OK"\n'
        '00456,2024-05-07,,"Test station"\n',
        media_type="Text/CSV; charset=utf-8",
    )
    original = item.path.read_bytes()
    provenance = item.provenance.model_dump()
    frame = item.open()
    assert frame.STATION.tolist() == ["00123", "00456"]
    assert frame.DATE.iloc[0] == "2024-05-06"
    assert frame.TMAX.iloc[0] == 25.5 and pd.isna(frame.TMAX.iloc[1])
    assert frame.NAME.iloc[0] == "Norman, OK"
    dated = item.open_csv(parse_dates=["DATE"], dtype={"STATION": "int64"}, nrows=1)
    assert dated.STATION.iloc[0] == 123
    assert dated.DATE.iloc[0] == pd.Timestamp("2024-05-06")
    assert len(dated) == 1
    frame.loc[0, "TMAX"] = 100
    assert item.path.read_bytes() == original and item.provenance.model_dump() == provenance
    assert frame.attrs["usdata"]["provenance"]["checksum"] == item.provenance.checksum


def test_usgs_codes_and_per_row_units_are_preserved(pd, fetched) -> None:
    frame = fetched(
        "monitoring_location_id,parameter_code,statistic_id,value,unit_of_measure\n"
        "07164500,00060,00003,7.5,ft3/s\n",
        dataset="usgs:water-daily",
    ).open()
    assert frame.monitoring_location_id.iloc[0] == "07164500"
    assert frame.parameter_code.iloc[0] == "00060"
    assert frame.statistic_id.iloc[0] == "00003"
    assert frame.value.iloc[0] == 7.5 and frame.unit_of_measure.iloc[0] == "ft3/s"


def test_erddap_units_are_metadata_not_observations(pd, fetched) -> None:
    item = fetched(
        "time,latitude,longitude,analysed_sst\nUTC,degrees_north,degrees_east,degree_C\n"
        "2024-05-06T12:00:00Z,30.025,-80.075,26.85\n"
        "2024-05-06T12:00:00Z,30.075,-80.075,27.15\n",
        protocol=Protocol.ERDDAP,
        dataset="noaa:coastwatch-sst",
    )
    # The public model must also work after deserializing a restored result.
    item = FetchedAsset.model_validate_json(item.model_dump_json())
    frame = item.open_csv(parse_dates=["time"], usecols=["time", "analysed_sst"])
    assert len(frame) == 2 and frame.analysed_sst.mean() == pytest.approx(27)
    assert frame.time.iloc[0] == pd.Timestamp("2024-05-06T12:00:00Z")
    assert frame.attrs["units"] == {"time": "UTC", "analysed_sst": "degree_C"}
    assert item.path.read_text().splitlines()[1].startswith("UTC,")


def test_explicit_reader_handles_ambiguous_metadata(pd, fetched) -> None:
    item = fetched("site_no,value\n00123,2\n", media_type=None)
    assert item.open_csv(units_row=False).site_no.iloc[0] == "00123"
    item = fetched("value\nmm\n2\n", media_type=None)
    frame = item.open_csv(units_row=True)
    assert frame.value.iloc[0] == 2 and frame.attrs["units"] == {"value": "mm"}


@pytest.mark.parametrize(
    "content,protocol",
    [
        ("", Protocol.HTTP),
        ("x,x\n1,2\n", Protocol.HTTP),
        ("x,\n1,2\n", Protocol.HTTP),
        ("x,y\nmm\n1,2\n", Protocol.ERDDAP),
        ("x,y\n", Protocol.ERDDAP),
    ],
)
def test_invalid_headers_fail_explicitly(pd, fetched, content, protocol) -> None:
    with pytest.raises(ValueError):
        fetched(content, protocol=protocol).open()


def test_header_only_and_missing_files(pd, fetched) -> None:
    item = fetched("STATION,TMAX\n")
    assert item.open().empty
    item.path.unlink()
    with pytest.raises(FileNotFoundError):
        item.open()


def test_fetch_open_does_not_change_sidecars_or_cached_results(pd, tmp_path: Path) -> None:
    with respx.mock() as mock:
        mock.get("https://www.ncei.noaa.gov/access/services/data/v1").mock(
            return_value=httpx.Response(200, text="STATION,DATE,TMAX\n00123,2024-05-06,25\n")
        )
        dataset = get("noaa:ghcn-daily")
        query = build_query(stations="00123", start="2024-05-06", end="2024-05-06")
        (item,) = fetch(dataset, query, root=tmp_path)
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    with respx.mock():
        assert item.open().TMAX.mean() == 25
        (cached,) = fetch(dataset, query, root=tmp_path)
        assert cached.from_cache and cached.open().STATION.iloc[0] == "00123"
    assert before == {path: path.read_bytes() for path in before}


def test_coops_fixture_uses_generic_csv_workflow(pd, fetched) -> None:
    source = (Path(__file__).parents[1] / "fixtures/coops-water-levels.csv").read_text()
    item = fetched(source, dataset="noaa:coops-water-levels")
    original = item.path.read_bytes()
    raw = item.open()
    assert " Quality " in raw.columns and " Water Level" in raw.columns
    frame = raw.rename(columns=str.strip)
    frame["Date Time"] = pd.to_datetime(frame["Date Time"], utc=True)
    assert frame["Date Time"].tolist() == list(
        pd.date_range("2024-05-06", periods=3, freq="6min", tz="UTC")
    )
    assert frame["Water Level"].tolist() == [1.765, 1.73, 1.702]
    assert frame["Quality"].tolist() == ["v", "v", "v"]
    assert {"O or I (for verified)", "F", "R", "L"}.issubset(frame.columns)
    assert frame.attrs["usdata"]["provenance"] == item.provenance.model_dump(mode="json")
    assert "units" not in frame.attrs
    assert item.path.read_bytes() == original


STORM_EVENTS_CSV = (
    "EVENT_ID,STATE,BEGIN_DATE_TIME,END_DATE_TIME,CZ_TIMEZONE\n"
    "1184052,OKLAHOMA,06-MAY-24 22:39:00,06-MAY-24 22:45:00,CST-6\n"
    "1200001,WASHINGTON,16-NOV-24 02:30:00,16-NOV-24 03:00:00,PST-8\n"
    "1200002,GUAM,01-JAN-24 00:00:00,01-JAN-24 06:00:00,GST10\n"
    "1200003,PUERTO RICO,02-FEB-24 03:00:00,02-FEB-24 04:00:00,AST\n"
)


def test_storm_events_gains_utc_columns_from_the_timezone_label(pd, fetched) -> None:
    item = fetched(STORM_EVENTS_CSV, dataset="noaa:storm-events")
    frame = item.open()
    assert frame.BEGIN_UTC.tolist()[:3] == [
        pd.Timestamp("2024-05-07T04:39:00Z"),
        pd.Timestamp("2024-11-16T10:30:00Z"),
        pd.Timestamp("2023-12-31T14:00:00Z"),
    ]
    assert frame.END_UTC.tolist()[:3] == [
        pd.Timestamp("2024-05-07T04:45:00Z"),
        pd.Timestamp("2024-11-16T11:00:00Z"),
        pd.Timestamp("2023-12-31T20:00:00Z"),
    ]
    assert pd.isna(frame.BEGIN_UTC.iloc[3]) and pd.isna(frame.END_UTC.iloc[3])
    assert str(frame.BEGIN_UTC.dtype).endswith("UTC]")
    assert frame.BEGIN_DATE_TIME.tolist() == [
        "06-MAY-24 22:39:00",
        "16-NOV-24 02:30:00",
        "01-JAN-24 00:00:00",
        "02-FEB-24 03:00:00",
    ]
    assert frame.CZ_TIMEZONE.tolist() == ["CST-6", "PST-8", "GST10", "AST"]
    derived = frame.attrs["usdata"]["derived"]
    assert [entry["column"] for entry in derived] == ["BEGIN_UTC", "END_UTC"]
    assert [entry["source"] for entry in derived] == ["BEGIN_DATE_TIME", "END_DATE_TIME"]
    assert [entry["unparsed"] for entry in derived] == [1, 1]
    assert [entry["labels_without_offset"] for entry in derived] == [{"AST": 1}, {"AST": 1}]
    assert all("CZ_TIMEZONE" in entry["rule"] for entry in derived)


BARE_LABEL_CSV = (
    "EVENT_ID,STATE,BEGIN_DATE_TIME,END_DATE_TIME,CZ_TIMEZONE\n"
    "1,OKLAHOMA,28-APR-50 14:45:00,28-APR-50 14:45:00,CST\n"
    "2,MARYLAND,31-DEC-68 23:30:00,01-JAN-69 00:30:00,EST\n"
    "3,MONTANA,04-JUL-99 12:00:00,04-JUL-99 13:00:00,MST\n"
    "4,CALIFORNIA,01-JAN-00 00:00:00,01-JAN-00 01:00:00,PST\n"
    "5,HAWAII,15-MAR-06 08:00:00,15-MAR-06 09:00:00,HST\n"
    "6,ALASKA,15-MAR-06 08:00:00,15-MAR-06 09:00:00,AST\n"
    "7,GUAM,15-MAR-06 08:00:00,15-MAR-06 09:00:00,SST\n"
    "8,WISCONSIN,15-JUN-06 08:00:00,15-JUN-06 09:00:00,CDT\n"
    "9,TEXAS,15-JUN-06 08:00:00,15-JUN-06 09:00:00,UNK\n"
    "10,TEXAS,15-JUN-06 08:00:00,15-JUN-06 09:00:00,\n"
)


def test_bare_labels_that_name_one_offset_everywhere_are_converted(pd, fetched) -> None:
    frame = fetched(BARE_LABEL_CSV, dataset="noaa:storm-events").open()
    assert frame.BEGIN_UTC.tolist()[:5] == [
        pd.Timestamp("1950-04-28T20:45:00Z"),
        pd.Timestamp("1969-01-01T04:30:00Z"),
        pd.Timestamp("1999-07-04T19:00:00Z"),
        pd.Timestamp("2000-01-01T08:00:00Z"),
        pd.Timestamp("2006-03-15T18:00:00Z"),
    ]
    # An event that ends after midnight on New Year's Eve crosses the century pivot cleanly.
    assert frame.END_UTC.iloc[1] == pd.Timestamp("1969-01-01T05:30:00Z")


def test_a_bare_daylight_label_is_read_at_its_word_like_one_that_states_its_offset(
    pd, fetched
) -> None:
    source = (
        "EVENT_ID,STATE,BEGIN_DATE_TIME,END_DATE_TIME,CZ_TIMEZONE\n"
        "1,WISCONSIN,15-JUN-06 08:00:00,15-JUN-06 09:00:00,CDT\n"
        "2,WISCONSIN,15-JUN-06 08:00:00,15-JUN-06 09:00:00,CDT-5\n"
        "3,VIRGINIA,15-JUN-06 08:00:00,15-JUN-06 09:00:00,EDT\n"
        "4,MONTANA,15-JUN-06 08:00:00,15-JUN-06 09:00:00,MDT\n"
    )
    frame = fetched(source, dataset="noaa:storm-events").open()
    assert frame.BEGIN_UTC.iloc[0] == frame.BEGIN_UTC.iloc[1] == pd.Timestamp("2006-06-15T13:00Z")
    assert frame.BEGIN_UTC.iloc[2] == pd.Timestamp("2006-06-15T12:00Z")
    assert frame.BEGIN_UTC.iloc[3] == pd.Timestamp("2006-06-15T14:00Z")
    assert frame.attrs["usdata"]["derived"][0]["labels_without_offset"] == {}


def test_bare_labels_that_name_two_offsets_or_none_are_left_unconverted(pd, fetched) -> None:
    frame = fetched(BARE_LABEL_CSV, dataset="noaa:storm-events").open()
    # AST is Alaska and Puerto Rico, SST is Samoa and Guam, and UNK says nothing.
    unconverted = frame[frame.CZ_TIMEZONE.isin(["AST", "SST", "UNK"]) | frame.CZ_TIMEZONE.isna()]
    assert len(unconverted) == 4
    assert unconverted.BEGIN_UTC.isna().all() and unconverted.END_UTC.isna().all()
    assert frame.BEGIN_UTC.notna().sum() == len(frame) - 4
    for entry in frame.attrs["usdata"]["derived"]:
        assert entry["unparsed"] == 4
        assert entry["labels_without_offset"] == {"AST": 1, "SST": 1, "UNK": 1}


@pytest.mark.filterwarnings("ignore:Could not infer format")  # The caller chose parse_dates.
def test_a_timestamp_column_the_caller_parsed_is_moved_back_to_the_archive_century(
    pd, fetched
) -> None:
    item = fetched(BARE_LABEL_CSV, dataset="noaa:storm-events")
    frame = item.open_csv(parse_dates=["BEGIN_DATE_TIME", "END_DATE_TIME"])
    assert frame.BEGIN_UTC.iloc[0] == pd.Timestamp("1950-04-28T20:45:00Z")
    assert frame.BEGIN_UTC.iloc[4] == pd.Timestamp("2006-03-15T18:00:00Z")


def test_the_1950_archive_file_lands_in_1950(pd, fetched) -> None:
    source = (Path(__file__).parents[1] / "fixtures/storm-details-1950.csv").read_text()
    frame = fetched(source, dataset="noaa:storm-events").open()
    assert len(frame) > 0 and frame.BEGIN_UTC.notna().all()
    assert set(frame.BEGIN_UTC.dt.year) == {1950}
    assert frame.BEGIN_UTC.iloc[0] == pd.Timestamp("1950-04-28T20:45:00Z")
    assert frame.attrs["usdata"]["derived"][0]["labels_without_offset"] == {}


def test_each_utc_column_needs_only_its_own_local_column(pd, fetched) -> None:
    item = fetched(STORM_EVENTS_CSV, dataset="noaa:storm-events")
    frame = item.open_csv(usecols=["EVENT_ID", "BEGIN_DATE_TIME", "CZ_TIMEZONE"])
    assert frame.BEGIN_UTC.iloc[0] == pd.Timestamp("2024-05-07T04:39:00Z")
    assert "END_UTC" not in frame.columns
    assert [entry["column"] for entry in frame.attrs["usdata"]["derived"]] == ["BEGIN_UTC"]


def test_a_local_column_without_its_timezone_warns_at_the_caller(pd, fetched) -> None:
    item = fetched(STORM_EVENTS_CSV, dataset="noaa:storm-events")
    with pytest.warns(UserWarning, match="without CZ_TIMEZONE, so BEGIN_UTC cannot") as caught:
        frame = item.open_csv(usecols=["EVENT_ID", "BEGIN_DATE_TIME"])
    assert caught[0].filename == __file__
    assert frame.columns.tolist() == ["EVENT_ID", "BEGIN_DATE_TIME"]
    assert frame.BEGIN_DATE_TIME.tolist()[0] == "06-MAY-24 22:39:00"
    assert "derived" not in frame.attrs["usdata"]


def test_a_frame_without_local_columns_is_left_alone(pd, fetched) -> None:
    item = fetched(STORM_EVENTS_CSV, dataset="noaa:storm-events")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        frame = item.open_csv(usecols=["EVENT_ID", "CZ_TIMEZONE"])
    assert frame.columns.tolist() == ["EVENT_ID", "CZ_TIMEZONE"]
    assert "derived" not in frame.attrs["usdata"]


def test_only_storm_events_assets_get_the_utc_columns(pd, fetched) -> None:
    frame = fetched(STORM_EVENTS_CSV, dataset="noaa:ghcn-daily").open()
    assert "BEGIN_UTC" not in frame.columns
    assert "derived" not in frame.attrs["usdata"]
