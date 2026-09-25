"""Atomic replacement helpers for downloads and JSON records."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

TEMP_SUFFIX = ".part"


def is_temporary(path: Path) -> bool:
    """Whether ``path`` is a temporary file ``staged_path`` made, finished or abandoned."""
    return path.name.startswith(".") and path.name.endswith(TEMP_SUFFIX)


@contextmanager
def staged_path(dest: Path) -> Iterator[Path]:
    """Replace dest only after successful work in a unique sibling temporary file.

    The file is flushed to disk before it replaces ``dest``, and the rename
    after, so once this returns the new ``dest`` survives a crash; without that
    a crash could keep the rename but lose the bytes, or reorder two renames.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        prefix=f".{dest.name}.", suffix=TEMP_SUFFIX, dir=dest.parent, delete=False
    ) as f:
        tmp = Path(f.name)
    try:
        yield tmp
        _fsync(tmp)
        tmp.replace(dest)
        _fsync_directory(dest.parent)
    finally:
        tmp.unlink(missing_ok=True)


def atomic_write_text(dest: Path, text: str) -> None:
    """Write UTF-8 text without exposing an incomplete record to readers."""
    with staged_path(dest) as tmp:
        tmp.write_text(text, encoding="utf-8")


def _fsync(path: Path) -> None:
    # Windows flushes only through a descriptor opened for writing.
    fd = os.open(path, os.O_RDWR)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_directory(path: Path) -> None:
    """Flush a directory's entries, where the platform allows opening a directory."""
    if os.name == "nt":
        return
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
