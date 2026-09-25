"""Small live IEM query, pinned and restored, opened with pandas when it is installed."""

import csv
from pathlib import Path

import pytest

from usdata.pull import pull, verify

pytestmark = pytest.mark.live


def test_the_warnings_issued_for_osage_county_on_the_evening_of_the_may_2024_outbreak(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: osage-warnings
sources:
  - name: evening
    dataset: noaa:nws-vtec-events
    location: Osage County, OK
    start: 2024-05-06T18:00Z
    end: 2024-05-07T12:00Z
  - name: inside-the-watch
    dataset: noaa:nws-vtec-events
    location: Osage County, OK
    start: 2024-05-07T03:00Z
    end: 2024-05-07T03:30Z
""")
    result = pull(manifest, root=tmp_path / "cache")
    with result.one("evening").path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows and {row["ugc"] for row in rows} == {"OKC113"}
    assert all(
        "2024-05-06T18:00:00Z" <= row["iso_issued"] <= "2024-05-07T12:00:00Z" for row in rows
    )
    warnings = [row for row in rows if (row["phenomena"], row["significance"]) == ("TO", "W")]
    # The warning in effect when the EF4 began at 02:12 UTC was issued at 01:56.
    assert "2024-05-07T01:56:00Z" in {row["iso_issued"] for row in warnings}
    watch = [row for row in rows if (row["phenomena"], row["significance"]) == ("TO", "A")]
    assert [(row["iso_issued"], row["iso_expired"]) for row in watch] == [
        ("2024-05-06T19:05:00Z", "2024-05-07T03:48:00Z")
    ]
    # A window inside that watch finds nothing: the service selects by issuance, not effect.
    with result.one("inside-the-watch").path.open(newline="") as f:
        assert list(csv.DictReader(f)) == []
    result.one("evening").path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and not restored.one("evening").from_cache
    assert verify(manifest, root=tmp_path / "cache") == []
    pandas = pytest.importorskip("pandas")
    frame = restored.one("evening").open_csv(parse_dates=["iso_issued", "iso_expired"])
    assert isinstance(frame, pandas.DataFrame) and len(frame) == len(rows)
    assert str(frame.iso_issued.dt.tz) == "UTC"
