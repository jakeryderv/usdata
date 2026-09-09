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
