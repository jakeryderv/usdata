"""ERSST v6 monthly global sea surface temperature from its NCEI HTTPS directory.

Both dates are required. Every calendar month the window touches is selected
whole: one global 2 degree NetCDF4 file per month, holding ``sst`` and ``ssta``,
the anomaly from ERSSTv6's own 1991-2020 climatology. The server does no
subsetting, so geographic, variable, and text filters are refused. Months run
from January 1850. Each monthly update writes the month just ended and rewrites
the month before it, so the newest file is preliminary until the next update.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.protocols.listing import directory_entries
from usdata.providers.base import QueryError
from usdata.providers.http import HttpProvider

DIRECTORY_URL = (
    "https://www.ncei.noaa.gov/data/sea-surface-temperature-extended-reconstructed/v6/access/"
)
FILE_NAME = re.compile(r"ersst\.v6\.(\d{4})(\d{2})\.nc", re.ASCII)
FIRST_MONTH = datetime(1850, 1, 1, tzinfo=UTC)
MEDIA_TYPE = "application/x-netcdf"


def month_starts(start: datetime, end: datetime) -> list[datetime]:
    """The first instant of every calendar month from ``start``'s through ``end``'s."""
    months = []
    month = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while month <= end:
        months.append(month)
        month = (month + timedelta(days=32)).replace(day=1)
    return months


def month_range(month: datetime) -> TimeRange:
    """The whole calendar month beginning at ``month``, to its last microsecond."""
    following = (month + timedelta(days=32)).replace(day=1)
    return TimeRange(start=month, end=following - timedelta(microseconds=1))


class Ersst(HttpProvider):
    """Resolve whole monthly ERSST v6 files; keep the NetCDF4 bytes exactly as published."""

    def list_assets(self, query: Query) -> list[Asset]:
        """One asset per calendar month the window touches, named as NCEI names the file."""
        self.check_params(query)
        self.reject(
            query,
            "bbox",
            "variables",
            "text",
            hint="ERSST files are whole global monthly grids holding sst and ssta; crop and "
            "select after opening",
        )
        start, end = self.utc_window(query)
        if start < FIRST_MONTH:
            raise QueryError("ERSST v6 monthly files start in January 1850")
        months = month_starts(start, end)
        page = http.get(DIRECTORY_URL, self._http()).text
        listed: dict[tuple[int, int], tuple[str, int | None]] = {}
        for name, size in directory_entries(page, FILE_NAME):
            match = FILE_NAME.fullmatch(name)
            assert match is not None
            listed[int(match[1]), int(match[2])] = name, size
        if not listed:
            raise QueryError(f"{DIRECTORY_URL} lists no ERSST v6 monthly files")
        if missing := [month for month in months if (month.year, month.month) not in listed]:
            latest = max(listed)
            raise QueryError(
                "no ERSST v6 file for "
                + ", ".join(f"{month:%Y-%m}" for month in missing)
                + f"; the newest published month is {latest[0]}-{latest[1]:02d}"
            )
        return [
            Asset(
                id=listed[month.year, month.month][0],
                dataset_id=self.dataset.id,
                href=DIRECTORY_URL + listed[month.year, month.month][0],
                protocol=Protocol.HTTP,
                media_type=MEDIA_TYPE,
                size=listed[month.year, month.month][1],
                time=month_range(month),
            )
            for month in months
        ]

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download one monthly file as published."""
        return http.download(asset.href, dest, self._http())
