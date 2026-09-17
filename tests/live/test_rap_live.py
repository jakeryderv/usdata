"""One RAP 13 km analysis: list with sizes, fetch two messages, restore, and open CAPE."""

from importlib.util import find_spec
from pathlib import Path

import pytest

from usdata import build_query, get
from usdata.providers import load_adapter
from usdata.pull import pull, verify

pytestmark = pytest.mark.live

MESSAGES = "CAPE:surface,HLCY:3000-0 m above ground"
MANIFEST = f"""name: rap-messages
sources:
  - dataset: noaa:rap
    start: 2024-05-06T20:00:00Z
    end: 2024-05-06T20:00:00Z
    params: {{cycle: 20, forecast_hour: 0, messages: "{MESSAGES}"}}
"""
WHOLE_BYTES = 18_368_480


def test_rap_listing_reports_sizes_before_download() -> None:
    with load_adapter(get("noaa:rap")) as adapter:
        listed = adapter.list_assets(
            build_query(
                start="2024-05-06T20:00Z", end="2024-05-06T20:00Z", cycle=20, forecast_hour="0,1"
            )
        )
    assert [asset.id for asset in listed] == [
        "rap.20240506.t20z.awp130pgrbf00.grib2",
        "rap.20240506.t20z.awp130pgrbf01.grib2",
    ]
    assert listed[0].size == WHOLE_BYTES


def test_rap_messages_fetch_restore_and_open(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    result = pull(manifest, root=tmp_path / "cache")
    (item,) = result.fetched
    assert item.provenance.is_partial and item.provenance.size < 200_000
    with item.path.open("rb") as stream:
        assert stream.read(4) == b"GRIB"
    item.path.unlink()
    again = pull(manifest, root=tmp_path / "cache")
    assert again.from_lockfile and again.lockfile == result.lockfile
    assert verify(manifest, root=tmp_path / "cache") == []
    if find_spec("eccodes") is None or find_spec("xarray") is None:
        pytest.skip("grib extra not installed")
    fields = again.fetched[0].open()
    names = {fields[name].attrs.get("GRIB_shortName", name) for name in fields.data_vars}
    assert {"cape", "hlcy"} <= names or len(fields.data_vars) == 2
    assert fields.latitude.shape == (337, 451)
