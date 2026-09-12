"""Small CO-OPS prediction requests beside observations, and pinned restoration."""

import csv
from importlib.util import find_spec
from pathlib import Path

import pytest

from usdata.pull import pull, verify

pytestmark = pytest.mark.live

MANIFEST = """name: battery-tide
sources:
  - dataset: noaa:coops-water-levels
    start: 2024-05-06T00:00:00Z
    end: 2024-05-06T00:12:00Z
    params: {station: "8518750", datum: MLLW, units: metric}
  - dataset: noaa:coops-tide-predictions
    start: 2024-05-06T00:00:00Z
    end: 2024-05-06T00:12:00Z
    params: {station: "8518750", datum: MLLW, units: metric}
  - dataset: noaa:coops-tide-predictions
    start: 2024-05-06T00:00:00Z
    end: 2024-05-07T00:00:00Z
    params: {station: "8518750", datum: MLLW, units: metric, interval: hilo}
"""


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as stream:
        return [
            {name.strip(): value.strip() for name, value in row.items()}
            for row in csv.DictReader(stream)
        ]


def test_coops_predictions_align_with_observations_and_restore(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    result = pull(manifest, root=tmp_path / "cache")
    observed, predicted, hilo = result.fetched
    assert predicted.asset.dataset_id == "noaa:coops-tide-predictions"
    observations, predictions, extremes = rows(observed.path), rows(predicted.path), rows(hilo.path)
    assert [row["Date Time"] for row in observations] == [row["Date Time"] for row in predictions]
    assert len(predictions) == 3
    assert all(-10 < float(row["Prediction"]) < 10 for row in predictions)
    assert 2 <= len(extremes) <= 5 and {row["Type"] for row in extremes} <= {"H", "L"}
    original = predicted.path.read_bytes()
    predicted.path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and restored.fetched[1].path.read_bytes() == original
    assert verify(manifest, root=tmp_path / "cache") == []
    if find_spec("pandas") is not None:
        frame = restored.fetched[1].open(parse_dates=["Date Time"])
        assert len(frame) == 3 and " Prediction" in frame.columns
