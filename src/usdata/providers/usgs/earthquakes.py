"""Earthquake events from the ANSS Comprehensive Catalog through the FDSN event service.

One anonymous REST service, ``https://earthquake.usgs.gov/fdsnws/event/1``,
answers bounding-box, time, magnitude, and depth filters and serves the result
as CSV: one row per event with its origin time, epicenter, depth, magnitude,
and review status. The columns are fixed, so ``variables`` is rejected and
rows are filtered locally.

The service caps one response at 20,000 events, so listing asks its ``count``
method first and makes one asset per page of that size, ordered by time
ascending so page membership is stable. Events are revised after publication
as networks review them, so a pinned page can change bytes; that is drift, not
an error in the adapter.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime
from pathlib import Path
from typing import Annotated

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.providers.base import QueryError
from usdata.providers.http import HttpProvider
from usdata.providers.params import number_range

SERVICE_URL = "https://earthquake.usgs.gov/fdsnws/event/1"
QUERY_URL = f"{SERVICE_URL}/query"
COUNT_URL = f"{SERVICE_URL}/count"
PAGE_SIZE = 20000
"""The most events one response may hold, the service's own limit."""


class EarthquakesParams(BaseModel):
    """Magnitude and depth bounds for one catalog query; the window and box come from the query."""

    model_config = ConfigDict(extra="forbid")

    min_magnitude: Annotated[float, number_range(-10, 10)] | None = Field(
        default=None, description="Smallest magnitude to include, inclusive."
    )
    max_magnitude: Annotated[float, number_range(-10, 10)] | None = Field(
        default=None, description="Largest magnitude to include, inclusive."
    )
    min_depth: Annotated[float, number_range(-100, 1000)] | None = Field(
        default=None, description="Shallowest depth to include, in kilometers, inclusive."
    )
    max_depth: Annotated[float, number_range(-100, 1000)] | None = Field(
        default=None, description="Deepest depth to include, in kilometers, inclusive."
    )

    @model_validator(mode="after")
    def _ordered_bounds(self) -> EarthquakesParams:
        """A lower bound above its upper bound selects nothing and is a mistake worth naming."""
        for low, high, what in (
            (self.min_magnitude, self.max_magnitude, "magnitude"),
            (self.min_depth, self.max_depth, "depth"),
        ):
            if low is not None and high is not None and low > high:
                raise ValueError(f"min_{what} must not exceed max_{what}")
        return self

    def filters(self) -> dict[str, str]:
        """The service parameters these bounds set, omitting the ones left at their default."""
        names = {
            "minmagnitude": self.min_magnitude,
            "maxmagnitude": self.max_magnitude,
            "mindepth": self.min_depth,
            "maxdepth": self.max_depth,
        }
        return {name: f"{value:g}" for name, value in names.items() if value is not None}


def _stamp(value: datetime) -> str:
    """A UTC instant as the service reads it: ISO 8601 with no offset, microseconds kept."""
    return value.replace(tzinfo=None).isoformat()


class Earthquakes(HttpProvider):
    """ComCat events as CSV pages; params bound magnitude and depth, the query gives the rest."""

    params_model = EarthquakesParams

    def list_assets(self, query: Query) -> list[Asset]:
        """One CSV asset per page of at most 20,000 events matching the window, box, and bounds."""
        params = self.parse_params(query, EarthquakesParams)
        self.reject(
            query,
            "text",
            "variables",
            hint="the CSV columns are fixed; filter rows and columns locally",
        )
        start, end = self.utc_window(query)
        window = TimeRange(start=start, end=end)
        filters = {"starttime": _stamp(start), "endtime": _stamp(end), **params.filters()}
        if query.bbox is not None:
            box = query.bbox
            filters.update(
                minlatitude=f"{box.south:g}",
                maxlatitude=f"{box.north:g}",
                minlongitude=f"{box.west:g}",
                maxlongitude=f"{box.east:g}",
            )
        count = self._count(filters)
        assets: list[Asset] = []
        for page in range(math.ceil(count / PAGE_SIZE)):
            url = httpx.URL(
                QUERY_URL,
                params={
                    **filters,
                    "format": "csv",
                    "orderby": "time-asc",
                    "limit": str(PAGE_SIZE),
                    "offset": str(1 + page * PAGE_SIZE),
                },
            )
            digest = hashlib.sha256(str(url).encode()).hexdigest()[:20]
            assets.append(
                Asset(
                    id=f"comcat_{start:%Y%m%d}_{end:%Y%m%d}_{digest}.csv",
                    dataset_id=self.dataset.id,
                    href=str(url),
                    protocol=Protocol.HTTP,
                    media_type="text/csv",
                    time=window,
                    bbox=query.bbox,
                )
            )
        return assets

    def _count(self, filters: dict[str, str]) -> int:
        """How many events the filters match, from the service's own count method."""
        response = http.get(COUNT_URL, self._http(), params=filters)
        text = response.text.strip()
        if not text.isdigit():
            raise QueryError(f"the catalog did not return a count for this query: {text[:200]!r}")
        return int(text)

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download one CSV page as the service serves it."""
        return http.download(asset.href, dest, self._http())
