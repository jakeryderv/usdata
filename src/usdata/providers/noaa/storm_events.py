"""Annual Storm Events details archives from the NCEI bulk directory.

Both dates are required. Every UTC calendar year touched by the interval is
selected in full; geographic, variable, text, and provider-specific filters are
unsupported. The most recently created supported details file wins per year.
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

DIRECTORY_URL = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
DETAILS_NAME = re.compile(r"StormEvents_details-ftp_v1\.0_d(\d{4})_c(\d{8})\.csv\.gz", re.ASCII)


class StormEvents(_HttpProvider):
    """Resolve whole-year details archives; preserve the original gzip bytes."""

    def list_assets(self, query: Query) -> list[Asset]:
        """Select the latest supported details revision for every requested year."""
        self.check_params(query)
        self.reject(
            query,
            "bbox",
            "variables",
            "text",
            hint="Storm Events downloads whole annual details files; filter locally after "
            "opening the CSV",
        )
        start, end = self.utc_window(query)
        if start.year < 1950:
            raise QueryError("Storm Events annual details files start in 1950")
        years = range(start.year, end.year + 1)
        page = http.get(DIRECTORY_URL, self._http()).text
        selected: dict[int, tuple[str, int | None]] = {}
        for name, size in directory_entries(page, DETAILS_NAME):
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
