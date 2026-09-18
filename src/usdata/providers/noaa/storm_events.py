"""Annual Storm Events archives from the NCEI bulk directory.

Both dates are required. Every UTC calendar year touched by the interval is
selected in full; geographic, variable, and text filters are unsupported. NCEI
publishes three tables per year under one naming and revision scheme, and
``table`` chooses one: ``details`` (the default, one row per event),
``fatalities`` (one row per death), or ``locations`` (one or more points per
event). ``EVENT_ID`` joins the other two to details; nothing is joined here.
The most recently created supported file of the chosen table wins per year.

Every table has a file for every year from 1950, but the locations files hold
rows only from 1996; earlier ones are a header and nothing else.
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

DIRECTORY_URL = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
TABLES = ("details", "fatalities", "locations")


def table_name(table: str) -> re.Pattern[str]:
    """The filename pattern of one table's annual files, capturing year and creation date."""
    return re.compile(
        rf"StormEvents_{re.escape(table)}-ftp_v1\.0_d(\d{{4}})_c(\d{{8}})\.csv\.gz", re.ASCII
    )


DETAILS_NAME = table_name("details")


class StormEventsParams(BaseModel):
    """Which of the three annual tables one Storm Events query names."""

    model_config = ConfigDict(extra="forbid")

    table: Annotated[str, choice(*TABLES)] = Field(
        default="details",
        description=(
            "Annual table: details (default, one row per event), fatalities (one row per "
            "death), or locations (points per event, from 1996); EVENT_ID joins them."
        ),
    )


class StormEvents(HttpProvider):
    """Resolve whole-year archives of one table; preserve the original gzip bytes."""

    params_model = StormEventsParams

    def list_assets(self, query: Query) -> list[Asset]:
        """Select the latest supported revision of the chosen table for every requested year."""
        table = self.parse_params(query, StormEventsParams).table
        self.reject(
            query,
            "bbox",
            "variables",
            "text",
            hint=f"Storm Events downloads whole annual {table} files; filter locally after "
            "opening the CSV",
        )
        start, end = self.utc_window(query)
        if start.year < 1950:
            raise QueryError(f"Storm Events annual {table} files start in 1950")
        years = range(start.year, end.year + 1)
        page = http.get(DIRECTORY_URL, self._http()).text
        pattern = table_name(table)
        selected: dict[int, tuple[str, int | None]] = {}
        for name, size in directory_entries(page, pattern):
            match = pattern.fullmatch(name)
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
                f"no supported Storm Events {table} file for year(s): " + ", ".join(missing)
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
