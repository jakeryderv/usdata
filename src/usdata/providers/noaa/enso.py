"""CPC's ENSO index tables: the official Relative Oceanic Niño Index and the traditional ONI.

Each index is one plain-text table on CPC's server holding its whole record,
one three-month season per row from DJF 1950, and CPC rewrites it in place each
month. ``index`` chooses the table: ``roni`` (the default), the Relative Oceanic
Niño Index that NOAA has used officially since 1 February 2026, or ``oni``, the
traditional Oceanic Niño Index. Both are computed from ERSST v6. There is no
selection by time or place, so a window, a box, variables, and text are refused;
listing makes no request and the size is left unknown.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.providers.http import HttpProvider
from usdata.providers.params import choice

INDEX_URL = "https://www.cpc.ncep.noaa.gov/data/indices/"
FILES = {"roni": "RONI.ascii.txt", "oni": "oni.ascii.txt"}
FIRST_SEASON = datetime(1949, 12, 1, tzinfo=UTC)
"""The first day of DJF 1950: CPC labels each season by the year of its middle month."""


class EnsoIndexParams(BaseModel):
    """Which of CPC's two ENSO index tables one query names."""

    model_config = ConfigDict(extra="forbid")

    index: Annotated[str, choice(*FILES)] = Field(
        default="roni",
        description=(
            "Index table: roni (default, the Relative Oceanic Niño Index NOAA uses "
            "officially) or oni (the traditional Oceanic Niño Index)."
        ),
    )


class EnsoIndices(HttpProvider):
    """Resolve one whole CPC index table; keep its text exactly as served."""

    params_model = EnsoIndexParams

    def list_assets(self, query: Query) -> list[Asset]:
        """The one table ``index`` names, holding every season from DJF 1950."""
        index = self.parse_params(query, EnsoIndexParams).index
        self.reject(
            query,
            "bbox",
            "variables",
            "text",
            "time",
            hint="each ENSO index table holds the whole record from DJF 1950; select seasons "
            "after reading it",
        )
        name = FILES[index]
        return [
            Asset(
                id=name,
                dataset_id=self.dataset.id,
                href=INDEX_URL + name,
                protocol=Protocol.HTTP,
                media_type="text/plain",
                time=TimeRange(start=FIRST_SEASON),
            )
        ]

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download the table as served."""
        return http.download(asset.href, dest, self._http())
