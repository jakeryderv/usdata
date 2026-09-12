"""Three days of LCD reports for one airport, report types, and pinned restoration."""

import csv
from collections import Counter
from importlib.util import find_spec
from pathlib import Path

import pytest

from usdata.pull import pull, verify

pytestmark = pytest.mark.live


def test_lcd_reports_and_daily_summaries_restore(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    example = Path(__file__).resolve().parents[2] / "examples/hourly-observations/dataset.yaml"
    manifest.write_bytes(example.read_bytes())
    result = pull(manifest, root=tmp_path / "cache")
    (item,) = result.fetched
    with item.path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    kinds = Counter(row["REPORT_TYPE"].strip() for row in rows)
    assert kinds["SOD"] == 3 and kinds["FM-15"] >= 60
    assert all(row["STATION"] == "72353013967" for row in rows)
    assert {row["DATE"][:10] for row in rows} == {"2024-05-06", "2024-05-07", "2024-05-08"}
    hourly = [
        float(row["HourlyDryBulbTemperature"].rstrip("s"))
        for row in rows
        if row["REPORT_TYPE"].strip() == "FM-15" and row["HourlyDryBulbTemperature"]
    ]
    assert all(-30 < value < 50 for value in hourly)
    original = item.path.read_bytes()
    item.path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and restored.fetched[0].path.read_bytes() == original
    assert verify(manifest, root=tmp_path / "cache") == []
    if find_spec("pandas") is not None:
        import pandas as pd

        frame = restored.fetched[0].open(parse_dates=["DATE"])
        kind = frame["REPORT_TYPE"].str.strip()
        day = frame["DATE"].dt.date
        temperature = pd.to_numeric(frame["HourlyDryBulbTemperature"], errors="coerce")
        hourly_max = temperature[kind == "FM-15"].groupby(day).max()
        summary = frame.loc[kind == "SOD"].set_index(day[kind == "SOD"])
        daily_max = pd.to_numeric(summary["DailyMaximumDryBulbTemperature"], errors="coerce")
        assert (hourly_max <= daily_max.loc[hourly_max.index] + 0.05).all()
