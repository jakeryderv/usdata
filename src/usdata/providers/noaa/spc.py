"""SPC tornado reports: whole annual or multi-year CSV files linked from one page.

The Storm Prediction Center publishes its tornado database as plain CSV files
linked from its severe weather database page: one file per year from 2008
onward, half-decade files for 2000-2007, and decade files for 1950-1999. Both
dates are required. Every file whose year range touches the UTC interval is
returned in full; geographic, variable, text, and provider-specific filters are
unsupported. File names are stable and bytes are revised in place, so a
lockfile checksum is the only revision record.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.protocols.listing import directory_entries
from usdata.providers._http import _HttpProvider
from usdata.providers.base import QueryError

PAGE_URL = "https://www.spc.noaa.gov/wcm/"
DATA_URL = "https://www.spc.noaa.gov/wcm/data/"
TABLE = "torn"
FIRST_YEAR = 1950
FILE_HREF = re.compile(rf"data/((\d{{2}}|\d{{4}})(?:-(\d{{2}}|\d{{4}}))?_{TABLE}\.csv)", re.ASCII)


def _year(raw: str) -> int:
    """A two-digit file year means the twentieth century; four digits are literal."""
    return 1900 + int(raw) if len(raw) == 2 else int(raw)


def file_years(href: str) -> tuple[str, int, int] | None:
    """The file name and inclusive first/last years of one linked tornado file, or None."""
    match = FILE_HREF.fullmatch(href)
    if match is None:
        return None
    first = _year(match[2])
    last = _year(match[3]) if match[3] else first
    if first < FIRST_YEAR or last < first:
        return None
    return match[1], first, last


class SpcTornadoReports(_HttpProvider):
    """Resolve the whole tornado files covering each requested year; fetch exact bytes."""

    def list_assets(self, query: Query) -> list[Asset]:
        """Select the narrowest linked file covering every requested year."""
        self.check_params(query)
        self.reject(
            query,
            "bbox",
            "variables",
            "text",
            hint="SPC downloads whole tornado files; filter locally after opening the CSV",
        )
        start, end = self.utc_window(query)
        if start.year < FIRST_YEAR:
            raise QueryError(f"SPC tornado reports start in {FIRST_YEAR}")
        years = range(start.year, end.year + 1)
        page = http.get(PAGE_URL, self._http()).text
        files: dict[str, tuple[int, int]] = {}
        for href, _size in directory_entries(page, FILE_HREF):
            parsed = file_years(href)
            if parsed is not None:
                files[parsed[0]] = parsed[1], parsed[2]
        selected: dict[int, str] = {}
        for year in years:
            covering = [name for name, (first, last) in files.items() if first <= year <= last]
            if covering:
                # A per-year file beats a decade file; the name breaks exact ties.
                selected[year] = min(
                    covering, key=lambda name: (files[name][1] - files[name][0], name)
                )
        if missing := [str(year) for year in years if year not in selected]:
            raise QueryError("no SPC tornado file for year(s): " + ", ".join(missing))
        names = sorted(set(selected.values()), key=lambda name: files[name])
        return [
            Asset(
                id=name,
                dataset_id=self.dataset.id,
                href=DATA_URL + name,
                protocol=Protocol.HTTP,
                media_type="text/csv",
                time=TimeRange(
                    start=datetime(files[name][0], 1, 1, tzinfo=UTC),
                    end=datetime(files[name][1], 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
                ),
            )
            for name in names
        ]

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download one pinned tornado file without subsetting."""
        return http.download(asset.href, dest, self._http())
