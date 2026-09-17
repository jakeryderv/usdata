"""One NBM CONUS hour: list with sizes, fetch the 2 m temperature message, restore, and open it."""

from importlib.util import find_spec
from pathlib import Path

import pytest

from usdata import build_query, get
from usdata.providers import load_adapter
from usdata.pull import pull, verify

pytestmark = pytest.mark.live

MANIFEST = """name: nbm-messages
sources:
  - dataset: noaa:nbm
    start: 2024-05-06T20:00:00Z
    end: 2024-05-06T20:00:00Z
    params: {cycle: 20, forecast_hour: 1, messages: "TMP:2 m above ground"}
"""
WHOLE_BYTES = 171_059_531


def test_nbm_listing_reports_sizes_before_download() -> None:
    with load_adapter(get("noaa:nbm")) as adapter:
        listed = adapter.list_assets(
            build_query(
                start="2024-05-06T20:00Z", end="2024-05-06T20:00Z", cycle=20, forecast_hour="1,3"
            )
        )
    assert [asset.id for asset in listed] == [
        "blend.20240506.t20z.core.f001.co.grib2",
        "blend.20240506.t20z.core.f003.co.grib2",
    ]
    assert listed[0].size == WHOLE_BYTES


def test_nbm_message_fetch_restore_and_open(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    result = pull(manifest, root=tmp_path / "cache")
    (item,) = result.fetched
    assert item.provenance.is_partial and 1_000_000 < item.provenance.size < 3_000_000
    item.path.unlink()
    again = pull(manifest, root=tmp_path / "cache")
    assert again.from_lockfile and again.lockfile == result.lockfile
    assert verify(manifest, root=tmp_path / "cache") == []
    if find_spec("eccodes") is None or find_spec("xarray") is None:
        pytest.skip("grib extra not installed")
    fields = again.fetched[0].open()
    (name,) = fields.data_vars
    assert fields[name].attrs["units"] == "K" and fields.latitude.shape == (1597, 2345)
