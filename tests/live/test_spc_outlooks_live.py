"""Small live IEM outlook archive queries: one issuance by its time, and an empty window."""

import struct
import zipfile
from pathlib import Path

import pytest

from usdata.pull import pull, verify

pytestmark = pytest.mark.live


def records(path: Path) -> int:
    """The row count a fetched zip's DBF header states."""
    with zipfile.ZipFile(path) as archive:
        (name,) = [name for name in archive.namelist() if name.endswith(".dbf")]
        return struct.unpack("<I", archive.read(name)[4:8])[0]


def test_the_outlook_issued_before_dawn_on_6_may_2024(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: outbreak-outlooks
sources:
  - name: overnight
    dataset: noaa:spc-outlooks
    start: 2024-05-06T05:00Z
    end: 2024-05-06T05:55Z
    params: {days: 1}
  - name: at-valid-start
    dataset: noaa:spc-outlooks
    start: 2024-05-06T12:00Z
    end: 2024-05-06T12:00:30Z
    params: {days: 1}
""")
    result = pull(manifest, root=tmp_path / "cache")
    # Issued at 05:55, the window's inclusive end, and valid from 12 UTC.
    assert records(result.one("overnight").path) == 19
    # Nothing is issued at the valid start: the window selects by issuance.
    with zipfile.ZipFile(result.one("at-valid-start").path) as archive:
        assert archive.namelist() == []
    result.one("overnight").path.unlink()
    restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and not restored.one("overnight").from_cache
    assert verify(manifest, root=tmp_path / "cache") == []
