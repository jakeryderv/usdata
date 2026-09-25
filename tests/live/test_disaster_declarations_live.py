"""Small live OpenFEMA query, pinned and restored, opened with pandas when it is installed."""

import csv
from pathlib import Path

import pytest

from usdata import build_query, fetch, get
from usdata.pull import pull, verify

pytestmark = pytest.mark.live


def test_connecticut_rows_still_carry_its_counties_before_2022(tmp_path: Path) -> None:
    query = build_query(location="Fairfield County, CT", start="2024-08-18", end="2024-08-19")
    (asset,) = fetch(get("fema:disaster-declarations"), query, root=tmp_path)
    with asset.path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    # DR-4820 designated Fairfield as 001, its legacy code, not as a planning region.
    assert "DR-4820-CT" in {row["femaDeclarationString"] for row in rows}
    assert {row["fipsCountyCode"] for row in rows} <= {"001", "000"}


def test_the_declaration_covering_the_may_2024_oklahoma_outbreak(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: oklahoma-declarations
sources:
  - name: state
    dataset: fema:disaster-declarations
    location: Oklahoma
    start: 2024-05-06
    end: 2024-05-06
    params: {declaration_type: DR}
  - name: county
    dataset: fema:disaster-declarations
    location: Osage County, OK
    start: 2024-05-06
    end: 2024-05-06
""")
    result = pull(manifest, root=tmp_path / "cache")
    with result.one("state").path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    # DR-4776 was declared on 30 April for an incident from 25 April to 9 May.
    assert rows and {row["femaDeclarationString"] for row in rows} == {"DR-4776-OK"}
    assert all(row["fipsStateCode"] == "40" and len(row["fipsCountyCode"]) == 3 for row in rows)
    assert all(row["incidentBeginDate"][:10] <= "2024-05-06" for row in rows)
    assert all(row["incidentEndDate"][:10] >= "2024-05-06" for row in rows)
    with result.one("county").path.open(newline="") as f:
        county = list(csv.DictReader(f))
    # A county selection is exact, and leaves out the never-closed fire declarations.
    assert [row["fipsCountyCode"] for row in county] == ["113"]
    assert all(row["incidentEndDate"] for row in county)
    result.one("state").path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and not restored.one("state").from_cache
    assert verify(manifest, root=tmp_path / "cache") == []
    pandas = pytest.importorskip("pandas")
    frame = restored.one("state").open()
    assert isinstance(frame, pandas.DataFrame) and len(frame) == len(rows)
    assert str(frame.fipsCountyCode.dtype) == "string"
