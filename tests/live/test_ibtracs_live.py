"""Live check: the South Atlantic IBTrACS files, the smallest subset (about 60 KB of CSV)."""

from pathlib import Path

import pytest

from usdata import fetch
from usdata.cache import sha256_file
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.live


def test_newest_version_csv_downloads_and_opens_with_units(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    (item,) = fetch(default_registry().get("noaa:ibtracs"), build_query(subset="sa"), root=tmp_path)
    assert item.asset.id.startswith("ibtracs.SA.list.v04r") and item.asset.id.endswith(".csv")
    assert item.provenance.checksum == sha256_file(item.path)
    assert item.asset.size == item.provenance.size
    span = item.asset.time
    assert span is not None and span.start is not None and span.end is not None
    assert span.start.year == 1842 and span.end.year >= 2026

    frame = item.open()
    assert (
        frame.attrs["units"]["USA_WIND"] == "kts" and frame.attrs["units"]["LAT"] == "degrees_north"
    )
    assert frame.BASIN.eq("SA").all() and frame.SID.nunique() >= 3  # Catarina 2004 among them.
    assert str(frame.USA_WIND.dtype) in {"int64", "float64"}
    assert frame.attrs["usdata"]["provenance"]["checksum"] == item.provenance.checksum


@pytest.mark.netcdf
def test_netcdf_format_opens_as_storm_by_time_arrays(tmp_path: Path) -> None:
    for dependency in ("xarray", "h5netcdf", "h5py"):
        pytest.importorskip(dependency)
    (item,) = fetch(
        default_registry().get("noaa:ibtracs"),
        build_query(subset="sa", format="netcdf"),
        root=tmp_path,
    )
    assert item.asset.id.startswith("IBTrACS.SA.v04r") and item.asset.id.endswith(".nc")
    data = item.open()
    assert set(data.dims) >= {"storm", "date_time"} and "usa_wind" in data
    assert data.attrs["usdata"]["asset_id"] == item.asset.id


def test_a_pinned_older_version_is_still_served(tmp_path: Path) -> None:
    (item,) = fetch(
        default_registry().get("noaa:ibtracs"),
        build_query(subset="sa", version="v04r00"),
        root=tmp_path,
    )
    assert item.asset.id == "ibtracs.SA.list.v04r00.csv" and item.provenance.size > 50_000
