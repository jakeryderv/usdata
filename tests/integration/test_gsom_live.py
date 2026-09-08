"""Bounded NCEI GSOM probes: one airport, one month, raw CSV restoration."""

import csv
import logging
from importlib.util import find_spec
from pathlib import Path

import pytest

from usdata.providers.noaa.gsom import GlobalSummaryMonthly
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.integration


def test_gsom_station_discovery(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="usdata.providers.noaa.ghcnd")
    query = build_query(
        bbox=(-97.62, 35.38, -97.58, 35.40),
        start="2024-05-06",
        end="2024-05-07",
        variables=["PRCP", "TAVG"],
    )
    with GlobalSummaryMonthly(default_registry().get("noaa:gsom")) as adapter:
        stations = adapter.find_stations(query)
    assert "USW00013967" in stations, f"GSOM search did not find OKC airport: {stations}"


def test_gsom_monthly_example_restore(tmp_path: Path) -> None:
    example = Path(__file__).resolve().parents[2] / "examples/monthly-climate/dataset.yaml"
    manifest = tmp_path / "dataset.yaml"
    manifest.write_bytes(example.read_bytes())
    result = pull(manifest, root=tmp_path / "cache")
    (item,) = result.fetched
    with item.path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1 and rows[0]["DATE"] == "2024-05"
    assert rows[0]["STATION"] == "USW00013967"
    assert float(rows[0]["PRCP"]) >= 0 and -60 < float(rows[0]["TAVG"]) < 60
    assert item.provenance.checksum.startswith("sha256:")
    item.path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and not restored.fetched[0].from_cache
    assert restored.lockfile == result.lockfile
    assert verify(manifest, root=tmp_path / "cache") == []
    # The weekly core profile still tests fetching and restoring without pandas.
    if find_spec("pandas") is None:
        return
    frame = restored.fetched[0].open()
    assert frame["DATE"].tolist() == ["2024-05"]
    assert frame["STATION"].tolist() == ["USW00013967"]
    assert frame.attrs["usdata"]["provenance"]["checksum"] == item.provenance.checksum
