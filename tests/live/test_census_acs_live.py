"""One live ACS table, pinned and restored, which only a response served identically allows.

Needs ``USDATA_CENSUS_KEY``: the Integration workflow sets it from a repository
secret, and a local run reads it from the environment.
"""

import json
import os
from pathlib import Path

import pytest

from usdata.pull import pull, verify

pytestmark = pytest.mark.live

VARIABLE = "USDATA_CENSUS_KEY"
MANIFEST = """name: oklahoma-counties
sources:
  - name: counties
    dataset: census:acs-5year
    location: Oklahoma
    variables: [NAME, B01003_001E, B01003_001M]
    params: {vintage: 2023, geography: county}
"""


@pytest.fixture(autouse=True)
def key() -> None:
    if not os.environ.get(VARIABLE, "").strip():
        pytest.skip(f"needs {VARIABLE} set; see docs/providers/census-acs-5year.md")


def test_oklahomas_counties_pin_restore_and_hold_no_key(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    root = tmp_path / "cache"
    item = pull(manifest, root=root).one("counties")
    header, *rows = json.loads(item.path.read_text())
    assert header == ["NAME", "B01003_001E", "B01003_001M", "state", "county"]
    # Oklahoma has 77 counties, and Osage (113) is one of them.
    assert len(rows) == 77 and ["40", "113"] in [row[3:] for row in rows]
    for path in root.rglob("*"):
        if path.is_file():
            assert os.environ[VARIABLE] not in path.read_text(), path
    # A fresh request must produce the same bytes, or the pin could never restore.
    item.path.unlink()
    restored = pull(manifest, root=root)
    assert restored.from_lockfile and not restored.one("counties").from_cache
    assert verify(manifest, root=root) == []
    pandas = pytest.importorskip("pandas")
    frame = restored.one("counties").open()
    assert isinstance(frame, pandas.DataFrame) and len(frame) == 77
    assert frame.B01003_001E.sum() > 3_900_000
    assert frame.attrs["usdata"]["properties"]["period"] == "2019-2023"
