import os
import sys
from pathlib import Path

import pytest

from usdata._files import atomic_write_text


def test_failed_atomic_write_keeps_previous_record(tmp_path: Path, monkeypatch) -> None:
    dest = tmp_path / "record.json"
    dest.write_text("original")

    def fail_replace(self, target):
        raise OSError("simulated interruption")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="interruption"):
        atomic_write_text(dest, "replacement")
    assert dest.read_text() == "original"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["record.json"]


@pytest.mark.skipif(sys.platform != "linux", reason="names descriptors through /proc")
def test_a_write_reaches_the_disk_before_its_rename_and_the_rename_after(
    tmp_path: Path, monkeypatch
) -> None:
    """A crash can keep a rename but lose unflushed bytes; ADR 0031 needs both flushed."""
    dest = tmp_path / "record.json"
    events: list[str] = []
    real_fsync, real_replace = os.fsync, Path.replace

    def fsync(fd: int) -> None:
        target = Path(os.readlink(f"/proc/self/fd/{fd}"))
        events.append("dir" if target.is_dir() else "file")
        real_fsync(fd)

    def replace(self: Path, target: Path) -> Path:
        events.append("rename")
        return real_replace(self, target)

    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr(Path, "replace", replace)
    atomic_write_text(dest, "record")
    assert events == ["file", "rename", "dir"]
    assert dest.read_text() == "record"
