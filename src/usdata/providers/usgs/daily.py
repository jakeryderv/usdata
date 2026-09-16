"""Daily values from the modern USGS Water Data OGC API.

Params: ``sites`` or ``site`` (USGS monitoring IDs, with or without the USGS-
prefix), and ``statistic_id`` (default 00003: daily mean). Variables are
five-digit parameter codes, such as 00060 for streamflow. Dates select inclusive
local calendar days; time-of-day information is discarded for daily values.

Listing probes one row at each page offset to learn how many pages exist without
downloading them. Each page is then fetched as the service's CSV representation,
preserving units, qualifiers, and approval status without the volatile GeoJSON
timeStamp.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from itertools import product
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.providers.base import QueryError
from usdata.providers.http import HttpProvider
from usdata.providers.params import StrList

ITEMS_URL = "https://api.waterdata.usgs.gov/ogcapi/v0/collections/daily/items"
PAGE_SIZE = 10000
MONITORING_ID = re.compile(r"USGS-\d{8,15}")
STATISTIC_ID = re.compile(r"\d{5}")


class WaterDailyParams(BaseModel):
    """Which USGS monitoring sites and daily statistic one query names."""

    model_config = ConfigDict(extra="forbid")

    site: StrList | None = Field(
        default=None, description="One USGS monitoring ID, with or without the USGS- prefix."
    )
    sites: StrList | None = Field(
        default=None, description="Several monitoring IDs, comma-separated or a list."
    )
    statistic_id: str = Field(
        default="00003", description="Five-digit statistic code; default 00003 (daily mean)."
    )

    @field_validator("statistic_id", mode="before")
    @classmethod
    def _five_digits(cls, value: object) -> object:
        """A leading zero only survives as text, so a bare number is a mistake worth naming."""
        if not isinstance(value, str) or not STATISTIC_ID.fullmatch(value):
            raise ValueError("must be a quoted five-digit code, for example 00003")
        return value

    @model_validator(mode="after")
    def _one_selector_of_monitoring_ids(self) -> WaterDailyParams:
        """``site`` and ``sites`` are alternatives, and either one names real monitoring ids."""
        if self.site is not None and self.sites is not None:
            raise ValueError("pass only one of site or sites")
        if any(not MONITORING_ID.fullmatch(value) for value in self.monitoring_ids):
            raise ValueError("sites must be USGS monitoring IDs, for example USGS-07164500")
        return self

    @property
    def monitoring_ids(self) -> list[str]:
        """Every requested site as a distinct prefixed id, in a stable order."""
        requested = self.sites if self.sites is not None else self.site
        return sorted({s if s.startswith("USGS-") else f"USGS-{s}" for s in requested or []})


class WaterDaily(HttpProvider):
    """USGS daily statistics as paginated CSV assets, with anonymous access."""

    params_model = WaterDailyParams

    def list_assets(self, query: Query) -> list[Asset]:
        """Resolve site or bbox queries to paginated CSV requests."""
        params = self.parse_params(query, WaterDailyParams)
        self.reject(query, "text", hint="select sites, a location, or parameter codes")
        start, end = self.utc_window(query)
        query = query.model_copy(update={"time": TimeRange(start=start, end=end)})
        site_filters: Sequence[str | None] = params.monitoring_ids or [None]
        if not params.monitoring_ids and query.bbox is None:
            raise QueryError(f"{self.dataset.id} needs a location, bbox, lat/lon, or sites=...")
        variables: Sequence[str | None] = sorted(set(query.variables)) or [None]
        if any(v is not None and not STATISTIC_ID.fullmatch(v) for v in variables):
            raise QueryError("variables must be five-digit USGS parameter codes, for example 00060")
        common = {
            "f": "json",
            "time": f"{start.date().isoformat()}/{end.date().isoformat()}",
            "statistic_id": params.statistic_id,
            "limit": str(PAGE_SIZE),
        }
        if query.bbox is not None:
            common["bbox"] = ",".join(str(v) for v in query.bbox.as_tuple())
        assets: list[Asset] = []
        for site, variable in product(site_filters, variables):
            filters = dict(common)
            if site is not None:
                filters["monitoring_location_id"] = site
            if variable is not None:
                filters["parameter_code"] = variable
            assets.extend(self._pages(filters, query))
        return assets

    def _pages(self, params: dict[str, str], query: Query) -> list[Asset]:
        assets: list[Asset] = []
        offset = 0
        while True:
            # A one-row probe says whether a page starts here; the CSV asset is the page.
            probe = httpx.URL(ITEMS_URL, params={**params, "limit": "1", "offset": str(offset)})
            response = http.get(probe, self._http())
            try:
                features = response.json()["features"]
                if not isinstance(features, list):
                    raise ValueError("features must be a list")
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                raise httpx.DecodingError("invalid USGS page", request=response.request) from e
            if not features:
                break
            url = httpx.URL(ITEMS_URL, params={**params, "offset": str(offset)})
            href = str(url.copy_set_param("f", "csv"))
            digest = hashlib.sha256(href.encode()).hexdigest()[:20]
            assets.append(
                Asset(
                    id=f"daily_{digest}.csv",
                    dataset_id=self.dataset.id,
                    href=href,
                    protocol=Protocol.HTTP,
                    media_type="text/csv",
                    time=query.time,
                    bbox=query.bbox,
                )
            )
            # The live service can fall back from a cursor link to offset=1 at the
            # end of a page, repeating records. Absolute offsets preserve the original
            # filters and avoid mixing pagination modes; sortby is not supported here.
            offset += PAGE_SIZE
        return assets

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download the server's CSV page without changing its data or metadata."""
        return http.download(asset.href, dest, self._http())
