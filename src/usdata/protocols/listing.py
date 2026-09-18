"""Read file names, byte sizes, and modified stamps from Apache-style HTML directory indexes."""

from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser
from typing import NamedTuple

MODIFIED = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}")
"""The minute-precision stamp Apache prints in a listing's "Last modified" column."""


class Entry(NamedTuple):
    """One file in a directory index: its name, byte size, and modified stamp, when listed.

    The stamp is naive: Apache prints it in the server's own timezone, which
    the caller knows and the listing does not say.
    """

    name: str
    size: int | None
    modified: datetime | None


class _Index(HTMLParser):
    """Collect entries for anchors whose href is a literal local file name.

    Only hrefs matching ``pattern`` in full are kept, so a listing can never
    steer a download to an arbitrary link. The size is the first all-digit
    table cell after the anchor's cell in the same row, and the modified
    stamp the first cell there holding a date and minute; either is None when
    the row has no such cell.
    """

    def __init__(self, pattern: re.Pattern[str]) -> None:
        super().__init__()
        self.pattern = pattern
        self.entries: list[Entry] = []
        self._in_row = False
        self._in_cell = False
        self._cells: list[str] = []
        self._name: str | None = None
        self._name_cell: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._end_row()  # Sloppy HTML may open a row without closing the last one.
            self._in_row, self._cells, self._name, self._name_cell = True, [], None, None
            self._in_cell = False
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
                self.entries.append(Entry(href, None, None))

    def handle_data(self, data: str) -> None:
        if self._in_cell and self._cells:
            self._cells[-1] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "td":
            self._in_cell = False
        elif tag == "tr":
            self._end_row()

    def _end_row(self) -> None:
        if self._in_row and self._name is not None:
            later = [c.strip() for c in self._cells[(self._name_cell or 0) + 1 :]]
            sizes = [c for c in later if c.isascii() and c.isdigit()]
            stamps = [m[0] for c in later if (m := MODIFIED.fullmatch(c))]
            modified = datetime.strptime(stamps[0], "%Y-%m-%d %H:%M") if stamps else None
            self.entries.append(Entry(self._name, int(sizes[0]) if sizes else None, modified))
        self._in_row, self._name = False, None


def directory_listing(html: str, pattern: re.Pattern[str]) -> list[Entry]:
    """Files matching ``pattern`` in a directory index, with size and modified stamp when listed."""
    index = _Index(pattern)
    index.feed(html)
    return index.entries


def directory_entries(html: str, pattern: re.Pattern[str]) -> list[tuple[str, int | None]]:
    """File names matching ``pattern`` in a directory index, with byte sizes when listed."""
    return [(entry.name, entry.size) for entry in directory_listing(html, pattern)]
