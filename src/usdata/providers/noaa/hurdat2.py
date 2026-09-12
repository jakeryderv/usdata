"""Whole-basin HURDAT2 best-track files from the National Hurricane Center.

The NHC publishes the complete best-track database as one fixed-format text file
per basin and revises it after each season. There is no query interface, so the
only sensible asset is the whole file: ``basin`` selects ``atlantic`` (default)
or ``pacific``, and the newest revision in the directory listing wins.

Dates, geographic filters, variables, text queries, and unknown params are
rejected rather than silently ignored: every revision contains the complete
record for its basin, so no date range could change what is downloaded. Asset
time bounds report the data span in the filename, not a requested window.
Filter the parsed track table locally with the ``hurdat2`` reader.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import ClassVar

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.protocols.listing import directory_entries
from usdata.providers._http import _HttpProvider
from usdata.providers.base import QueryError

DIRECTORY_URL = "https://www.nhc.noaa.gov/data/hurdat/"
# hurdat2[-<basin>]-<first year>-<last year>-<revision>[<letter>].txt; the Atlantic
# basin token is usually omitted. Revisions are MMDDYY or MMDDYYYY, never YYYYMMDD.
FILE_NAME = re.compile(r"hurdat2-(?:(atl|nepac)-)?(\d{4})-(\d{4})-(\d{6}|\d{8})([a-z]?)\.txt")
BASIN_TOKENS = {"atlantic": frozenset({"", "atl"}), "pacific": frozenset({"nepac"})}


def _revision(value: str) -> date | None:
    """The revision date encoded in a filename, or None if it is not a real date."""
    try:
        return datetime.strptime(value, "%m%d%Y" if len(value) == 8 else "%m%d%y").date()
    except ValueError:
        return None


class Hurdat2(_HttpProvider):
    """Resolve one whole-basin best-track file; preserve the original text bytes."""

    accepted_params: ClassVar[Mapping[str, str]] = {
        "basin": "Best-track basin: 'atlantic' (default) or 'pacific'.",
    }

    def list_assets(self, query: Query) -> list[Asset]:
        """Select the newest revision of the requested basin's complete database."""
        self.check_params(query)
        requested = query.params.get("basin", "atlantic")
        basin = requested.strip().casefold() if isinstance(requested, str) else ""
        if basin not in BASIN_TOKENS:
            raise QueryError(
                f"unsupported HURDAT2 basin {requested!r}; use 'atlantic' (default) or 'pacific'"
            )
        self.reject(
            query,
            "bbox",
            "variables",
            "text",
            hint="HURDAT2 publishes one whole text file per basin; filter the parsed track "
            "table locally",
        )
        self.reject(
            query,
            "time",
            hint="every revision holds the complete basin record, so a date range would not "
            "change the download; remove start/end and filter the parsed 'time' column locally",
        )
        page = http.get(DIRECTORY_URL, self._http()).text
        candidates = []
        for name, size in directory_entries(page, FILE_NAME):
            match = FILE_NAME.fullmatch(name)
            assert match is not None
            first, last, revised = int(match[2]), int(match[3]), _revision(match[4])
            if (match[1] or "") not in BASIN_TOKENS[basin] or revised is None or first > last:
                continue
            # Prefer the latest season covered, then the newest revision of that span.
            candidates.append(((last, revised, name), first, last, size))
        if not candidates:
            raise QueryError(f"no HURDAT2 {basin} best-track file in the NHC directory listing")
        (_, _, name), first, last, size = max(candidates)
        return [
            Asset(
                id=name,
                dataset_id=self.dataset.id,
                href=DIRECTORY_URL + name,
                protocol=Protocol.HTTP,
                media_type="text/plain",
                size=size,
                time=TimeRange(
                    start=datetime(first, 1, 1, tzinfo=UTC),
                    end=datetime(last, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
                ),
            )
        ]

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download the pinned revision, without reformatting or subsetting it."""
        return http.download(asset.href, dest, self._http())
