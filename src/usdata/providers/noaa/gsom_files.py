"""Whole Global Summary of the Month station files from NCEI's static access directory.

One CSV per station holds that station's whole monthly record, every element
with its ``_ATTRIBUTES`` column, in metric units. NCEI serves them as plain
files, so a station is one GET that does not depend on the Access Data
Service. ``stations`` is required. A window, a box, variables, and text are
refused, because a file is always the whole record of every element. The
directory is too large to list, so listing makes no request, and a station
with no file fails at fetch with a 404. A file's span is known only once it
is read, so an asset's time is bounded by the archive itself, as IBTrACS bounds
its complete record.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.providers.http import HttpProvider
from usdata.providers.params import UpperStrList

ACCESS_URL = "https://www.ncei.noaa.gov/data/global-summary-of-the-month/access/"
STATION_ID = re.compile(r"[A-Z0-9]{11}", re.ASCII)
ARCHIVE_START = datetime(1763, 1, 1, tzinfo=UTC)
"""GHCN-Daily's first observation, so no GSOM station file can begin earlier."""


def station_ids(value: list[str]) -> list[str]:
    """Keep each GHCN station id once, in request order, refusing anything else."""
    if bad := [station for station in value if not STATION_ID.fullmatch(station)]:
        raise ValueError(f"must be 11-character GHCN station ids, not {', '.join(bad)}")
    return list(dict.fromkeys(value))


class GsomFileParams(BaseModel):
    """Which stations' whole monthly files one query names."""

    model_config = ConfigDict(extra="forbid")

    stations: Annotated[UpperStrList, AfterValidator(station_ids)] = Field(
        description="Required GHCN station id(s): one, a list, or comma-separated."
    )


class GsomStationFiles(HttpProvider):
    """Resolve one whole monthly CSV per station; keep the bytes exactly as NCEI serves them."""

    params_model = GsomFileParams

    def list_assets(self, query: Query) -> list[Asset]:
        """One asset per requested station, in request order, without any request."""
        stations = self.parse_params(query, GsomFileParams).stations
        self.reject(
            query,
            "bbox",
            "variables",
            "text",
            "time",
            hint="each GSOM station file holds the station's whole record of every element; "
            "name stations and select months and columns after opening",
        )
        return [
            Asset(
                id=f"{station}.csv",
                dataset_id=self.dataset.id,
                href=f"{ACCESS_URL}{station}.csv",
                protocol=Protocol.HTTP,
                media_type="text/csv",
                time=TimeRange(start=ARCHIVE_START),
                properties={"units": "metric"},
            )
            for station in stations
        ]

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download one station's file as served."""
        return http.download(asset.href, dest, self._http())
