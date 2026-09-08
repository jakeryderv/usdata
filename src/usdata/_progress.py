"""Internal synchronous progress events, scoped to one CLI operation."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Batch:
    """A resolved group; sizes describe assets, including possible cache hits."""

    count: int
    known_bytes: int
    unknown_sizes: int


@dataclass(frozen=True)
class AssetProgress:
    """Start or validated completion of an asset."""

    asset_id: str
    state: Literal["start", "cached", "fetched"]
    size: int | None


@dataclass(frozen=True)
class TransferProgress:
    """Bytes written in the current HTTP attempt, reset on every retry."""

    completed: int
    total: int | None
    attempt: int


Event = Batch | AssetProgress | TransferProgress
_observer: ContextVar[Callable[[Event], None] | None] = ContextVar("progress", default=None)


def emit(event: Event) -> None:
    """Notify the active observer without importing CLI code."""
    observer = _observer.get()
    if observer is not None:
        observer(event)


def batch(sizes: Sequence[int | None]) -> None:
    """Report known and unknown sizes separately; never guess a total."""
    emit(Batch(len(sizes), sum(size for size in sizes if size is not None), sizes.count(None)))


@contextmanager
def observe(callback: Callable[[Event], None]) -> Iterator[None]:
    """Observe an operation and restore the previous observer on every exit."""
    token = _observer.set(callback)
    try:
        yield
    finally:
        _observer.reset(token)
