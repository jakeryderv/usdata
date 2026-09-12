"""Read file names and byte sizes from Apache-style HTML directory indexes."""

from __future__ import annotations

import re
from html.parser import HTMLParser


class _Index(HTMLParser):
    """Collect (name, size) for anchors whose href is a literal local file name.

    Only hrefs matching ``pattern`` in full are kept, so a listing can never
    steer a download to an arbitrary link. The size is the first all-digit
    table cell after the anchor's cell in the same row, or None.
    """

    def __init__(self, pattern: re.Pattern[str]) -> None:
        super().__init__()
        self.pattern = pattern
        self.entries: list[tuple[str, int | None]] = []
        self._in_row = False
        self._in_cell = False
        self._cells: list[str] = []
        self._name: str | None = None
        self._name_cell: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._in_row, self._cells, self._name, self._name_cell = True, [], None, None
        elif tag == "td":
            self._cells.append("")
            self._in_cell = True
        elif tag == "a":
            href = dict(attrs).get("href", "") or ""
            if not self.pattern.fullmatch(href):
                return
            if self._in_row:
                self._name, self._name_cell = href, len(self._cells) - 1
            else:
                self.entries.append((href, None))

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cells[-1] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "td":
            self._in_cell = False
        elif tag == "tr":
            if self._name is not None:
                later = self._cells[(self._name_cell or 0) + 1 :]
                sizes = [c.strip() for c in later if c.strip().isascii() and c.strip().isdigit()]
                self.entries.append((self._name, int(sizes[0]) if sizes else None))
            self._in_row = False


def directory_entries(html: str, pattern: re.Pattern[str]) -> list[tuple[str, int | None]]:
    """File names matching ``pattern`` in a directory index, with byte sizes when listed."""
    index = _Index(pattern)
    index.feed(html)
    return index.entries
