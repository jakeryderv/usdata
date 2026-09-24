"""One live AQS site-day, pinned and restored, which only a stable canonical form allows.

Needs ``USDATA_AQS_EMAIL`` and ``USDATA_AQS_KEY``: the Integration workflow sets
them from repository secrets, and a local run reads them from the environment.
"""

import json
import os
from pathlib import Path

import pytest

from usdata.pull import pull, verify

pytestmark = pytest.mark.live

VARIABLES = ("USDATA_AQS_EMAIL", "USDATA_AQS_KEY")
MANIFEST = """name: queens-smoke-day
sources:
  - name: queens
    dataset: epa:aqs-daily
    start: 2023-06-07
    end: 2023-06-07
    params: {parameters: 88101, sites: 36-081-0124}
"""


@pytest.fixture(autouse=True)
def keys() -> None:
    if missing := [name for name in VARIABLES if not os.environ.get(name, "").strip()]:
        pytest.skip(f"needs {', '.join(missing)} set; see docs/providers/epa-aqs-daily.md")


def test_the_smoke_day_at_queens_college_pins_restores_and_holds_no_key(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    root = tmp_path / "cache"
    item = pull(manifest, root=root).one("queens")
    body = json.loads(item.path.read_text())
    assert body["Header"][0]["status"] == "Success" and "url" not in body["Header"][0]
    rows = body["Data"]
    assert rows and {(r["site_number"], r["date_local"]) for r in rows} == {("0124", "2023-06-07")}
    daily = [r["arithmetic_mean"] for r in rows if r["pollutant_standard"] == "PM25 24-hour 2024"]
    # Canadian wildfire smoke put the day far above the 35 ug/m3 daily standard.
    assert daily and max(daily) > 35
    for path in root.rglob("*"):
        if path.is_file():
            text = path.read_text()
            assert not any(os.environ[name] in text for name in VARIABLES), path
    # A fresh request must produce the same bytes, or the pin could never restore.
    item.path.unlink()
    restored = pull(manifest, root=root)
    assert restored.from_lockfile and not restored.one("queens").from_cache
    assert verify(manifest, root=root) == []
    pandas = pytest.importorskip("pandas")
    frame = restored.one("queens").open()
    assert isinstance(frame, pandas.DataFrame) and len(frame) == len(rows)
    assert (frame.date_local == pandas.Timestamp("2023-06-07")).all()
