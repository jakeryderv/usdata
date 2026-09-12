"""GHCN-Daily via the NCEI Access Data Service.

Two NCEI endpoints are involved:

- the *search* service resolves a bounding box and date range to station ids;
- the *data* service returns observations for explicit stations as CSV.

The data service rejects spatial filters for this dataset, so a bbox query
always goes through search first. Stations are chunked so URLs stay short.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

import httpx

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.providers._http import _HttpProvider
from usdata.providers.base import QueryError

SEARCH_URL = "https://www.ncei.noaa.gov/access/services/search/v1/data"
DATA_URL = "https://www.ncei.noaa.gov/access/services/data/v1"
NCEI_DATASET = "daily-summaries"
SEARCH_PAGE_SIZE = 1000
STATIONS_PER_ASSET = 50
logger = logging.getLogger(__name__)


def _date(value: Any) -> str:
    return value.strftime("%Y-%m-%d")


def _stations_param(raw: Any) -> list[str]:
    if isinstance(raw, str):
        raw = raw.split(",")
    if not isinstance(raw, (list, tuple)) or not all(isinstance(s, str) for s in raw):
        raise QueryError("stations must be a string or list of strings")
    stations = list(dict.fromkeys(s.strip() for s in raw if s.strip()))
    if not stations:
        raise QueryError("stations must not be empty")
    return stations


class GhcnDaily(_HttpProvider):
    """GHCN-Daily adapter. Params: ``stations`` (list or comma string), ``units``."""

    accepted_params: ClassVar[Mapping[str, str]] = {
        "stations": "Station ids, comma-separated or a list; otherwise a location selects them.",
        "units": "metric (default) or standard.",
    }
    ncei_dataset = NCEI_DATASET

    def find_stations(self, query: Query) -> list[str]:
        """Station ids with data inside the query's bbox and time range."""
        return self._search_stations(self.ncei_dataset, query)

    def _search_stations(self, ncei_dataset: str, query: Query) -> list[str]:
        """Page through the NCEI search service for one dataset's stations."""
        if query.bbox is None or query.time is None:
            raise QueryError("station search needs a bounding box and a time range")
        b = query.bbox
        params: dict[str, Any] = {
            "dataset": ncei_dataset,
            "bbox": f"{b.north},{b.west},{b.south},{b.east}",
            "startDate": _date(query.time.start),
            "endDate": _date(query.time.end),
            "limit": SEARCH_PAGE_SIZE,
            "offset": 0,
        }
        if query.variables:
            params["dataTypes"] = ",".join(query.variables)
        found: list[str] = []
        seen: set[str] = set()
        while True:
            resp = http.get(SEARCH_URL, self._http(), params=params)
            body = resp.json()
            results = body.get("results", [])
            before = len(found)
            for result in results:
                for station in result.get("stations", []):
                    sid = station.get("id")
                    if sid and sid not in seen:
                        seen.add(sid)
                        found.append(sid)
            logger.debug(
                "NCEI station search: url=%s status=%s content_type=%s "
                "count=%r totalCount=%r results=%s new_stations=%s station_sample=%r",
                resp.request.url,
                resp.status_code,
                resp.headers.get("content-type"),
                body.get("count"),
                body.get("totalCount"),
                len(results),
                len(found) - before,
                found[before : before + 5],
            )
            if len(found) == before and logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "NCEI search page yielded no new stations; response_prefix=%r", resp.text[:512]
                )
            # "count" is the number matching this query; "totalCount" is dataset-wide.
            params["offset"] += SEARCH_PAGE_SIZE
            if not results or params["offset"] >= int(body.get("count", 0)):
                break
        return found

    def _chunk_size(self) -> int:
        """Stations per CSV asset; subclasses with wide rows lower it."""
        return STATIONS_PER_ASSET

    def _units(self, query: Query) -> str:
        units = query.params.get("units", "metric")
        if units not in ("metric", "standard"):
            raise QueryError("units must be metric or standard")
        return units

    def _stations(self, query: Query) -> list[str]:
        """Explicit ``stations`` or the ones found inside the bbox, never a mix of both."""
        if "stations" in query.params and query.bbox is not None:
            raise QueryError("pass stations or a location/bbox, not both")
        if "stations" in query.params:
            return _stations_param(query.params["stations"])
        if query.bbox is not None:
            return self.find_stations(query)
        raise QueryError(f"{self.dataset.id} needs a location, bbox, or stations=...")

    def list_assets(self, query: Query) -> list[Asset]:
        """One CSV asset per chunk of up to STATIONS_PER_ASSET stations for the query window."""
        self.check_params(query)
        self.reject(query, "text", hint="search the registry instead")
        start_at, end_at = self.utc_window(query)
        window = TimeRange(start=start_at, end=end_at)
        query = query.model_copy(update={"time": window})
        units = self._units(query)
        stations = self._stations(query)
        if not stations:
            return []

        start, end = _date(window.start), _date(window.end)
        assets: list[Asset] = []
        size = self._chunk_size()
        for i in range(0, len(stations), size):
            chunk = stations[i : i + size]
            params: dict[str, Any] = {
                "dataset": self.ncei_dataset,
                "stations": ",".join(chunk),
                "startDate": start,
                "endDate": end,
                "format": "csv",
                "units": units,
                "includeStationLocation": "1",
            }
            if query.variables:
                params["dataTypes"] = ",".join(query.variables)
            url = str(httpx.URL(DATA_URL, params=params))
            digest = hashlib.sha1(url.encode()).hexdigest()[:12]
            assets.append(
                Asset(
                    id=f"{self.ncei_dataset}_{start}_{end}_{digest}.csv",
                    dataset_id=self.dataset.id,
                    href=url,
                    protocol=Protocol.HTTP,
                    media_type="text/csv",
                    time=window,
                    bbox=query.bbox,
                )
            )
        return assets

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Stream the CSV response to ``dest``."""
        return http.download(asset.href, dest, self._http())
