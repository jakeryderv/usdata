"""Annual Storm Events details archives from the NCEI bulk directory.

Both dates are required. Every UTC calendar year touched by the interval is
selected in full; geographic, variable, text, and provider-specific filters are
unsupported. The most recently created supported details file wins per year.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.providers._http import _HttpProvider
from usdata.providers.base import QueryError

DIRECTORY_URL = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
DETAILS_NAME = re.compile(r"StormEvents_details-ftp_v1\.0_d(\d{4})_c(\d{8})\.csv\.gz", re.ASCII)


class _Directory(HTMLParser):
    """Read filenames and exact byte sizes from NCEI's HTML directory table."""

    def __init__(self) -> None:
        super().__init__()
        self.files: list[tuple[str, int | None]] = []
        self._cells: list[str] = []
        self._name: str | None = None
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._cells, self._name = [], None
        elif tag == "td":
            self._cells.append("")
            self._in_cell = True
        elif tag == "a":
            href = dict(attrs).get("href", "") or ""
            # Only literal local filenames; never follow arbitrary links from a listing.
            if DETAILS_NAME.fullmatch(href):
                self._name = href

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cells[-1] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "td":
            self._in_cell = False
        elif tag == "tr" and self._name is not None:
            size = self._cells[2].strip() if len(self._cells) > 2 else ""
            self.files.append(
                (self._name, int(size) if size.isascii() and size.isdigit() else None)
            )


class StormEvents(_HttpProvider):
    """Resolve whole-year details archives; preserve the original gzip bytes."""

    def list_assets(self, query: Query) -> list[Asset]:
        """Select the latest supported details revision for every requested year."""
        if unknown := set(query.params) - set(self.params):
            raise QueryError(f"unsupported Storm Events params: {', '.join(sorted(unknown))}")
        if query.bbox is not None or query.variables or query.text:
            raise QueryError(
                "Storm Events downloads whole annual details files; location/bbox, variables, "
                "and text filters are unsupported. Filter locally after opening the CSV."
            )
        if query.time is None or query.time.start is None or query.time.end is None:
            raise QueryError(f"{self.dataset.id} requires both start and end dates")
        start = query.time.start.replace(tzinfo=query.time.start.tzinfo or UTC).astimezone(UTC)
        end = query.time.end.replace(tzinfo=query.time.end.tzinfo or UTC).astimezone(UTC)
        if start.year < 1950:
            raise QueryError("Storm Events annual details files start in 1950")
        years = range(start.year, end.year + 1)
        listing = _Directory()
        listing.feed(http.get(DIRECTORY_URL, self._http()).text)
        selected: dict[int, tuple[str, int | None]] = {}
        for name, size in listing.files:
            match = DETAILS_NAME.fullmatch(name)
            assert match is not None
            year = int(match[1])
            if year not in years:
                continue
            try:
                datetime.strptime(match[2], "%Y%m%d")
            except ValueError:
                continue
            # Fixed-width YYYYMMDD names sort by creation date. Duplicate rows are harmless.
            if year not in selected or name > selected[year][0]:
                selected[year] = name, size
        if missing := [str(year) for year in years if year not in selected]:
            raise QueryError(
                "no supported Storm Events details file for year(s): " + ", ".join(missing)
            )
        return [
            Asset(
                id=selected[year][0],
                dataset_id=self.dataset.id,
                href=DIRECTORY_URL + selected[year][0],
                protocol=Protocol.HTTP,
                media_type="application/gzip",
                size=selected[year][1],
                time=TimeRange(
                    start=datetime(year, 1, 1, tzinfo=UTC),
                    end=datetime(year, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
                ),
            )
            for year in years
        ]

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download the pinned annual archive, without decompressing or subsetting."""
        return http.download(asset.href, dest, self._http())
