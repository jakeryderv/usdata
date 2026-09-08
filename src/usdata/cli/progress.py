"""Terminal-only progress rendering; normal CLI output remains machine readable."""

from __future__ import annotations

import shutil
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from time import monotonic
from typing import TextIO

from usdata._progress import AssetProgress, Batch, Event, observe


def _interactive() -> bool:
    return sys.stdout.isatty() and sys.stderr.isatty()


class _Display:
    def __init__(self, stream: TextIO) -> None:
        self.stream = stream
        self.width = 0
        self.updated = 0.0
        self.asset = ""
        self.count = 0
        self.done = 0
        self.cached = 0

    def clear(self) -> None:
        if self.width:
            self.stream.write("\r" + " " * self.width + "\r")
            self.stream.flush()
            self.width = 0

    def line(self, text: str, *, final: bool = False) -> None:
        self.clear()
        # IDs come from providers: keep control characters out of the terminal.
        text = "".join(c if c.isprintable() else "?" for c in text)
        if final:
            self.stream.write(text + "\n")
        else:
            text = text[: max(1, shutil.get_terminal_size().columns - 1)]
            self.stream.write(text)
            self.width = len(text)
        self.stream.flush()
        self.updated = monotonic()

    def __call__(self, event: Event) -> None:
        if isinstance(event, Batch):
            self.count, self.done, self.cached = event.count, 0, 0
            sizes = f"{event.known_bytes:,} known bytes"
            if event.unknown_sizes:
                sizes += f"; {event.unknown_sizes} size(s) unknown"
            self.line(f"{event.count} asset(s) resolved; {sizes} (before cache checks)", final=True)
        elif isinstance(event, AssetProgress):
            self.asset = event.asset_id
            if event.state == "start":
                size = f"{event.size:,} bytes" if event.size is not None else "size unknown"
                self.line(f"[{self.done}/{self.count}] checking cache ({size}) | {self.asset}")
            else:
                self.done += 1
                self.cached += event.state == "cached"
                self.line(
                    f"[{self.done}/{self.count}] {event.state} "
                    f"({event.size:,} bytes; {self.cached} cached) | {self.asset}",
                    final=self.done == self.count,
                )
        else:
            if event.completed and monotonic() - self.updated < 0.1:
                return
            size = f"{event.total:,}" if event.total is not None else "unknown"
            self.line(
                f"[{self.done}/{self.count}] {event.completed:,}/{size} bytes "
                f"(attempt {event.attempt}) | {self.asset}"
            )


@contextmanager
def progress(*, disabled: bool = False) -> Iterator[None]:
    """Render progress on stderr only when both output streams are terminals."""
    if disabled or not _interactive():
        yield
        return
    display = _Display(sys.stderr)
    with observe(display):
        try:
            yield
        finally:
            display.clear()
