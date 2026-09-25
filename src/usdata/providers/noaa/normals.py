"""U.S. Climate Normals 1991-2020 through the NCEI Access Data Service.

Params: ``period`` (``monthly`` by default, ``daily``, ``annualseasonal``, or ``hourly``),
``stations`` (list or comma string), and ``units`` (metric or standard).

Normals are 30-year averages, not observations, so dates are optional. For hourly,
daily, and monthly normals an optional ``start``/``end`` pair selects a calendar window
by month and day; the year is ignored and sent as the placeholder 2020, a leap
year so February 29 is valid. Windows cannot cross the new year. Without dates
the whole year is requested. Annual/seasonal normals accept no dates. Assets
carry the 1991-2020 normals period as their time bounds.
Hourly normals return all hours of each selected day, labeled in local standard
time as ``MM-DDTHH:MM:SS``. They have no February 29 values.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
from pydantic import Field

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.providers.base import QueryError, to_utc
from usdata.providers.noaa.ghcnd import DATA_URL, STATIONS_PER_ASSET, GhcnDaily, GhcnDailyParams
from usdata.providers.params import choice

PERIODS = {
    "monthly": "normals-monthly-1991-2020",
    "daily": "normals-daily-1991-2020",
    "annualseasonal": "normals-annualseasonal-1991-2020",
    "hourly": "normals-hourly-1991-2020",
}
PLACEHOLDER_YEAR = 2020
NORMALS_PERIOD = TimeRange(
    start=datetime(1991, 1, 1, tzinfo=UTC),
    end=datetime(2020, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
)


class ClimateNormalsParams(GhcnDailyParams):
    """A normals query also names which averaging period it wants."""

    period: Annotated[str, choice(*PERIODS)] = Field(
        default="monthly", description="monthly (default), daily, annualseasonal, or hourly."
    )


def _window(query: Query, period: str) -> tuple[str, str] | None:
    """The startDate/endDate pair to send, or None for annual/seasonal normals."""
    start = query.time.start if query.time else None
    end = query.time.end if query.time else None
    if period == "annualseasonal":
        if start is not None or end is not None:
            raise QueryError("annualseasonal normals do not accept dates")
        return None
    if start is None and end is None:
        return (f"{PLACEHOLDER_YEAR}-01-01", f"{PLACEHOLDER_YEAR}-12-31")
    if start is None or end is None:
        raise QueryError("pass both start and end dates, or neither for the whole year")
    first, last = to_utc(start), to_utc(end)
    if (first.month, first.day) > (last.month, last.day):
        raise QueryError("normals windows cannot cross the new year; split the query")
    return (
        f"{PLACEHOLDER_YEAR}-{first.month:02d}-{first.day:02d}",
        f"{PLACEHOLDER_YEAR}-{last.month:02d}-{last.day:02d}",
    )


class ClimateNormals(GhcnDaily):
    """1991-2020 normals as CSV subsets, reusing NCEI station discovery and transport."""

    params_model = ClimateNormalsParams

    def find_stations(self, query: Query) -> list[str]:
        """Stations with normals for the selected period inside the query's bbox."""
        dataset = PERIODS[self.parse_params(query, ClimateNormalsParams).period]
        return self._search_stations(dataset, query.model_copy(update={"time": NORMALS_PERIOD}))

    def list_assets(self, query: Query) -> list[Asset]:
        """One CSV asset per chunk of stations for the selected period and window."""
        params = self.parse_params(query, ClimateNormalsParams)
        self.reject(query, "text", hint="search the registry instead")
        window = _window(query, params.period)
        stations = self._stations(query, params.stations)
        if not stations:
            return []

        ncei_dataset = PERIODS[params.period]
        label = ncei_dataset
        if window is not None:
            label = f"{ncei_dataset}_{window[0][5:]}_{window[1][5:]}"
        assets: list[Asset] = []
        for i in range(0, len(stations), STATIONS_PER_ASSET):
            chunk = stations[i : i + STATIONS_PER_ASSET]
            request: dict[str, Any] = {
                "dataset": ncei_dataset,
                "stations": ",".join(chunk),
                "format": "csv",
                "units": params.units,
                "includeStationLocation": "1",
            }
            if window is not None:
                request["startDate"], request["endDate"] = window
            if query.variables:
                request["dataTypes"] = ",".join(query.variables)
            url = str(httpx.URL(DATA_URL, params=request))
            digest = hashlib.sha1(url.encode()).hexdigest()[:12]
            assets.append(
                Asset(
                    id=f"{label}_{digest}.csv",
                    dataset_id=self.dataset.id,
                    href=url,
                    protocol=Protocol.HTTP,
                    media_type="text/csv",
                    time=NORMALS_PERIOD,
                    bbox=query.bbox,
                    properties={"units": params.units},
                )
            )
        return assets
