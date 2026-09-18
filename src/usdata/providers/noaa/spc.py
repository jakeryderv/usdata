"""SPC severe weather reports: whole annual or multi-year CSV files linked from one page.

The Storm Prediction Center publishes its tornado, hail, and wind databases as
plain CSV files linked from its severe weather database page, in one layout: one
file per year from 2008 onward, half-decade files for 2000-2007, and decade
files before that. ``table`` chooses ``torn`` (the default), ``hail``, or
``wind``. The tornado files start in 1950; the hail and wind files start in
1955. Both dates are required. Every file of the chosen table whose year range
touches the UTC interval is returned in full; geographic, variable, and text
filters are unsupported. File names are stable and bytes are revised in place,
so a lockfile checksum is the only revision record.

The three tables share their columns, and ``mag`` means something different in
each: the F or EF rating for a tornado, with ``-9`` for unknown, the stone
diameter in inches for hail, and the speed in knots for wind. Wind adds ``mt``,
how that speed was obtained, and tornado adds ``fc``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.protocols.listing import directory_entries
from usdata.providers.base import QueryError
from usdata.providers.http import HttpProvider
from usdata.providers.params import choice

PAGE_URL = "https://www.spc.noaa.gov/wcm/"
DATA_URL = "https://www.spc.noaa.gov/wcm/data/"
FIRST_YEARS = {"torn": 1950, "hail": 1955, "wind": 1955}
"""Each table and the first year SPC publishes it for."""

LABELS = {"torn": "tornado", "hail": "hail", "wind": "wind"}


def file_href(table: str) -> re.Pattern[str]:
    """The link pattern of one table's files, capturing the name and its first and last year."""
    return re.compile(
        rf"data/((\d{{2}}|\d{{4}})(?:-(\d{{2}}|\d{{4}}))?_{re.escape(table)}\.csv)", re.ASCII
    )


def _year(raw: str) -> int:
    """A two-digit file year means the twentieth century; four digits are literal."""
    return 1900 + int(raw) if len(raw) == 2 else int(raw)


def file_years(href: str, table: str = "torn") -> tuple[str, int, int] | None:
    """The file name and inclusive first/last years of one linked file of ``table``, or None."""
    match = file_href(table).fullmatch(href)
    if match is None:
        return None
    first = _year(match[2])
    last = _year(match[3]) if match[3] else first
    if first < FIRST_YEARS[table] or last < first:
        return None
    return match[1], first, last


class SpcReportsParams(BaseModel):
    """Which of the three report tables one SPC query names."""

    model_config = ConfigDict(extra="forbid")

    table: Annotated[str, choice(*FIRST_YEARS)] = Field(
        default="torn",
        description=(
            "Report table: torn (default, from 1950), hail (from 1955), or wind (from 1955); "
            "mag is the F/EF rating, inches, or knots respectively."
        ),
    )


class SpcTornadoReports(HttpProvider):
    """Resolve the whole files of one table covering each requested year; fetch exact bytes."""

    params_model = SpcReportsParams

    def list_assets(self, query: Query) -> list[Asset]:
        """Select the narrowest linked file of the chosen table covering every requested year."""
        table = self.parse_params(query, SpcReportsParams).table
        label = LABELS[table]
        self.reject(
            query,
            "bbox",
            "variables",
            "text",
            hint=f"SPC downloads whole {label} files; filter locally after opening the CSV",
        )
        start, end = self.utc_window(query)
        if start.year < FIRST_YEARS[table]:
            raise QueryError(f"SPC {label} reports start in {FIRST_YEARS[table]}")
        years = range(start.year, end.year + 1)
        page = http.get(PAGE_URL, self._http()).text
        files: dict[str, tuple[int, int]] = {}
        for href, _size in directory_entries(page, file_href(table)):
            parsed = file_years(href, table)
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
            raise QueryError(f"no SPC {label} file for year(s): " + ", ".join(missing))
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
        """Download one pinned report file without subsetting."""
        return http.download(asset.href, dest, self._http())
