"""Atomic replacement helpers for downloads and JSON records."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile


@contextmanager
def staged_path(dest: Path) -> Iterator[Path]:
    """Replace dest only after successful work in a unique sibling temporary file."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        prefix=f".{dest.name}.", suffix=".part", dir=dest.parent, delete=False
    ) as f:
        tmp = Path(f.name)
    try:
        yield tmp
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)


def atomic_write_text(dest: Path, text: str) -> None:
    """Write UTF-8 text without exposing an incomplete record to readers."""
    with staged_path(dest) as tmp:
        tmp.write_text(text, encoding="utf-8")
