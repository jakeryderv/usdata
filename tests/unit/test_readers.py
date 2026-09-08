from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from usdata import build_query, get
from usdata.fetch import FetchedAsset, fetch
from usdata.models import Asset, Protocol, Provenance
from usdata.readers import MissingReaderDependency, UnsupportedFormat


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


def test_broken_pandas_dependency_is_not_misreported(fetched) -> None:
    item = fetched("STATION,TMAX\n00123,25\n")
    with (
        patch("usdata.readers.import_module", side_effect=ModuleNotFoundError(name="numpy")),
        pytest.raises(ModuleNotFoundError) as error,
    ):
        item.open()
    assert error.value.name == "numpy"


@pytest.mark.parametrize("media_type", [None, "application/octet-stream", "application/x-netcdf"])
def test_unsupported_formats_do_not_load_pandas(fetched, media_type) -> None:
    item = fetched("not CSV", media_type=media_type)
    with (
        patch("usdata.readers.import_module") as loader,
        pytest.raises(UnsupportedFormat, match=r"fetched\.path"),
    ):
        item.open()
    loader.assert_not_called()


def test_unknown_reader_rejected(fetched) -> None:
    with pytest.raises(UnsupportedFormat, match="unsupported reader"):
        fetched("x\n1\n").open(reader="pickle")


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
    dated = item.open(parse_dates=["DATE"], dtype={"STATION": "int64"}, nrows=1)
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
    frame = item.open(parse_dates=["time"], usecols=["time", "analysed_sst"])
    assert len(frame) == 2 and frame.analysed_sst.mean() == pytest.approx(27)
    assert frame.time.iloc[0] == pd.Timestamp("2024-05-06T12:00:00Z")
    assert frame.attrs["units"] == {"time": "UTC", "analysed_sst": "degree_C"}
    assert item.path.read_text().splitlines()[1].startswith("UTC,")


def test_explicit_reader_handles_ambiguous_metadata(pd, fetched) -> None:
    item = fetched("site_no,value\n00123,2\n", media_type=None)
    assert item.open(reader="csv").site_no.iloc[0] == "00123"
    item = fetched("value\nmm\n2\n", media_type=None)
    frame = item.open(reader="erddap-csv")
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
