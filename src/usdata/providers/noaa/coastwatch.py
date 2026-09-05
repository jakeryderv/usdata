"""CoastWatch blended day/night SST as reproducible ERDDAP CSV subsets.

Requires bbox and inclusive UTC start/end timestamps. Dates mean midnight UTC.
Variables default to analysed_sst; stride optionally subsamples both spatial
axes by a positive integer. Empty intersections resolve to no assets. Requests
exceeding one million grid rows must be narrowed or use a larger stride.
"""

from __future__ import annotations

import hashlib
import math
from bisect import bisect_left, bisect_right
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import cast

import httpx

from usdata.models import Asset, BBox, Dataset, Protocol, Query, TimeRange
from usdata.protocols import erddap, http
from usdata.providers.base import Provider, QueryError

BASE = "https://coastwatch.noaa.gov/erddap"
DATASET = "noaacwBLENDEDsstDNDaily"
VARIABLES = {"analysed_sst", "analysis_error", "sea_ice_fraction", "mask"}
MAX_ROWS = 1_000_000


def _spatial_slice(
    low: float, high: float, origin: float, count: int, stride: int
) -> tuple[erddap.GridSlice, int] | None:
    first = max(0, math.ceil((low - origin) / 0.05 - 1e-9))
    last = min(count - 1, math.floor((high - origin) / 0.05 + 1e-9))
    if first > last:
        return None
    length = (last - first) // stride + 1
    last = first + (length - 1) * stride
    return erddap.GridSlice(
        round(origin + first * 0.05, 6), round(origin + last * 0.05, 6), stride
    ), length


class CoastwatchSst(Provider):
    """NOAA's 0.05-degree day/night analysis, including units and grid coordinates."""

    def __init__(self, dataset: Dataset, client: httpx.Client | None = None) -> None:
        super().__init__(dataset)
        self._client = client
        self._owns_client = client is None

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = http.client()
        return self._client

    def close(self) -> None:
        """Release owned connections; injected clients remain the caller's responsibility."""
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def list_assets(self, query: Query) -> list[Asset]:
        """Resolve a valid grid intersection into one stable, bounded CSV request."""
        if (
            query.bbox is None
            or query.time is None
            or query.time.start is None
            or query.time.end is None
        ):
            raise QueryError(
                f"{self.dataset.id} requires a bbox/location and both start and end times"
            )
        if unknown := set(query.params) - {"stride"}:
            raise QueryError(f"unsupported CoastWatch params: {', '.join(sorted(unknown))}")
        stride = query.params.get("stride", 1)
        if isinstance(stride, str) and stride.isascii() and stride.isdigit():
            stride = int(stride)
        if type(stride) is not int or stride < 1:
            raise QueryError("stride must be a positive integer")
        variables = sorted(set(query.variables)) if query.variables else ["analysed_sst"]
        if unsupported := set(variables) - VARIABLES:
            raise QueryError(f"unsupported CoastWatch variables: {', '.join(sorted(unsupported))}")
        lat = _spatial_slice(query.bbox.south, query.bbox.north, -89.975, 3600, stride)
        lon = _spatial_slice(query.bbox.west, query.bbox.east, -179.975, 7200, stride)
        if lat is None or lon is None:
            return []
        metadata = erddap.info(BASE, DATASET, self._http())
        try:
            if metadata.dimensions["latitude"] != 3600 or metadata.dimensions["longitude"] != 7200:
                raise ValueError("spatial dimensions changed")
            for name, expected in (
                ("latitude", (-89.975, 89.975)),
                ("longitude", (-179.975, 179.975)),
            ):
                actual = tuple(
                    float(v) for v in metadata.attributes[name]["actual_range"].split(",")
                )
                if actual != expected:
                    raise ValueError("spatial coordinates changed")
            if any(
                metadata.variables[name] != ("time", "latitude", "longitude") for name in variables
            ):
                raise ValueError("variable dimensions changed")
            units, raw_times = erddap.axis(BASE, DATASET, "time", self._http())
            times = [datetime.fromisoformat(value) for value in raw_times]
            if any(value.tzinfo is None for value in times):
                raise ValueError("time axis must include UTC offsets")
            times = [value.astimezone(UTC) for value in times]
            if units != "UTC" or any(a >= b for a, b in pairwise(times)):
                raise ValueError("unexpected time axis")
        except (KeyError, TypeError, ValueError) as error:
            raise httpx.DecodingError("CoastWatch grid metadata changed or is invalid") from error
        first = bisect_left(times, query.time.start)
        last = bisect_right(times, query.time.end) - 1
        if first > last:
            return []
        if (last - first + 1) * lat[1] * lon[1] > MAX_ROWS:
            raise QueryError(
                "CoastWatch subset exceeds 1,000,000 rows; narrow bbox/time or increase stride"
            )
        href = erddap.griddap_url(
            BASE, DATASET, variables, [erddap.GridSlice(times[first], times[last]), lat[0], lon[0]]
        )
        digest = hashlib.sha256(href.encode()).hexdigest()[:20]
        # Spatial slices here always use numeric coordinate values.
        bbox = BBox(
            west=cast(float, lon[0].start),
            south=cast(float, lat[0].start),
            east=cast(float, lon[0].stop),
            north=cast(float, lat[0].stop),
        )
        return [
            Asset(
                id=f"sst_{digest}.csv",
                dataset_id=self.dataset.id,
                href=href,
                protocol=Protocol.ERDDAP,
                media_type="text/csv",
                bbox=bbox,
                time=TimeRange(start=times[first], end=times[last]),
            )
        ]

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download raw ERDDAP CSV, retaining its coordinate columns and units row."""
        return http.download(asset.href, dest, self._http())
