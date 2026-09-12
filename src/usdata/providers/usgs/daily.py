"""Daily values from the modern USGS Water Data OGC API.

Params: ``sites`` or ``site`` (USGS monitoring IDs, with or without the USGS-
prefix), and ``statistic_id`` (default 00003: daily mean). Variables are
five-digit parameter codes, such as 00060 for streamflow. Dates select inclusive
local calendar days; time-of-day information is discarded for daily values.

Each result page is fetched as the service's CSV representation, preserving
units, qualifiers, and approval status without the volatile GeoJSON timeStamp.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from itertools import product
from pathlib import Path
from typing import ClassVar

import httpx

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.providers._http import _HttpProvider
from usdata.providers.base import QueryError

ITEMS_URL = "https://api.waterdata.usgs.gov/ogcapi/v0/collections/daily/items"
PAGE_SIZE = 10000


def _values(raw: object, name: str) -> list[str]:
    if isinstance(raw, str):
        values = raw.split(",")
    elif isinstance(raw, (list, tuple)) and all(isinstance(v, str) for v in raw):
        values = raw
    else:
        raise QueryError(f"{name} must be a string or list of strings; quote numeric codes")
    cleaned = sorted({v.strip() for v in values if v.strip()})
    if not cleaned:
        raise QueryError(f"{name} must not be empty")
    return cleaned


class WaterDaily(_HttpProvider):
    """USGS daily statistics as paginated CSV assets, with anonymous access."""

    accepted_params: ClassVar[Mapping[str, str]] = {
        "site": "One USGS monitoring ID, with or without the USGS- prefix.",
        "sites": "Several monitoring IDs, comma-separated or a list.",
        "statistic_id": "Five-digit statistic code; default 00003 (daily mean).",
    }

    def list_assets(self, query: Query) -> list[Asset]:
        """Resolve site or bbox queries to paginated CSV requests."""
        self.check_params(query)
        self.reject(query, "text", hint="select sites, a location, or parameter codes")
        start, end = self.utc_window(query)
        query = query.model_copy(update={"time": TimeRange(start=start, end=end)})
        if "site" in query.params and "sites" in query.params:
            raise QueryError("pass only one of site or sites")
        raw_sites = query.params.get("sites", query.params.get("site"))
        site_filters: Sequence[str | None] = [None]
        if raw_sites is not None:
            ids = _values(raw_sites, "sites")
            normalized = [s if s.startswith("USGS-") else f"USGS-{s}" for s in ids]
            if any(not re.fullmatch(r"USGS-\d{8,15}", s) for s in normalized):
                raise QueryError("sites must be USGS monitoring IDs, for example USGS-07164500")
            site_filters = sorted(set(normalized))
        elif query.bbox is None:
            raise QueryError(f"{self.dataset.id} needs a location, bbox, lat/lon, or sites=...")
        variables: Sequence[str | None] = sorted(set(query.variables)) or [None]
        statistic = query.params.get("statistic_id", "00003")
        if not isinstance(statistic, str) or not re.fullmatch(r"\d{5}", statistic):
            raise QueryError("statistic_id must be a quoted five-digit code, for example 00003")
        if any(v is not None and not re.fullmatch(r"\d{5}", v) for v in variables):
            raise QueryError("variables must be five-digit USGS parameter codes, for example 00060")
        params = {
            "f": "json",
            "time": f"{start.date().isoformat()}/{end.date().isoformat()}",
            "statistic_id": statistic,
            "limit": str(PAGE_SIZE),
        }
        if query.bbox is not None:
            params["bbox"] = ",".join(str(v) for v in query.bbox.as_tuple())
        assets: list[Asset] = []
        for site, variable in product(site_filters, variables):
            filters = dict(params)
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
            url = httpx.URL(ITEMS_URL, params={**params, "offset": str(offset)})
            response = http.get(url, self._http())
            response.raise_for_status()
            try:
                body = response.json()
                features = body["features"]
                if not isinstance(features, list):
                    raise ValueError("features must be a list")
                links = body.get("links", [])
                next_url = next((link["href"] for link in links if link.get("rel") == "next"), None)
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                raise httpx.DecodingError("invalid USGS page", request=response.request) from e
            if not features:
                break
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
            if next_url is None:
                break
            # The live service can fall back from a cursor link to offset=1 at the
            # end of a page, repeating records. Absolute offsets preserve the original
            # filters and avoid mixing pagination modes; sortby is not supported here.
            offset += len(features)
        return assets

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download the server's CSV page without changing its data or metadata."""
        return http.download(asset.href, dest, self._http())
