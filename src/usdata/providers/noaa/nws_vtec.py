"""NWS watch, warning, and advisory events for one county or zone, from IEM's archive.

The Iowa Environmental Mesonet mirrors National Weather Service products and
serves the events issued for one UGC, the NWS code for a county or a forecast
zone, as CSV: one row per event with its issuance and expiry, its VTEC
phenomena and significance, the issuing office, and the product id. The archive
reaches back to 1986 for tornado, severe thunderstorm, and flash flood
warnings, and to 2005 or 2008 for most other products. The official NWS API
keeps no archive.

The rows carry no coordinates, so this is a source keyed by place: a county
``location`` selects that county's UGC exactly, and a bare ``bbox`` or
``lat``/``lon`` is refused (ADR 0034). A county UGC is the state's postal code,
``C``, and the three-digit county FIPS code, so Osage County, Oklahoma is
``OKC113``.

Three things about the service shape the queries, each learned by getting it
wrong first (ADR 0036):

- The date-only ``sdate`` and ``edate`` parameters are unreliable: a span that
  returns thirteen rows when given as explicit datetimes returns none when given
  as dates. Only ``sts`` and ``ets`` are sent.
- The window selects by issuance, not by what was in effect. A watch issued
  before the window and still running through it is not returned; the service
  cannot be asked what was in effect, only what was issued.
- A county code reaches county-based products only: tornado, severe
  thunderstorm, and flash flood events. Winter, heat, wind, and fire products
  are issued by forecast zone, which a county location cannot name; ``ugc``
  reaches one explicitly.

``ets`` is exclusive where a usdata window's end is inclusive, so one second is
added to the end sent. Listing makes no request: there is no count to ask for,
so a window with no events fetches a header and no rows rather than listing
nothing, and an explicit ``ugc`` the service does not know does the same.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.providers.base import QueryError
from usdata.providers.http import HttpProvider

SERVICE_URL = "https://mesonet.agron.iastate.edu/json/vtec_events_byugc.py"
_UGC = re.compile(r"[A-Z]{2}[CZ]\d{3}")
_PHENOMENA = re.compile(r"[A-Z]{2}")
_SIGNIFICANCE = re.compile(r"[A-Z]")


class VtecEventsParams(BaseModel):
    """What one events query names beyond its window; the county comes from the query."""

    model_config = ConfigDict(extra="forbid")

    ugc: str | None = Field(
        default=None,
        description=(
            "One NWS UGC code in place of a location: a county such as OKC113, or a forecast "
            "zone such as OKZ054, which is the only way to reach zone-based products."
        ),
    )
    phenomena: str | None = Field(
        default=None,
        description="Two-letter VTEC phenomena such as TO or SV; requires significance.",
    )
    significance: str | None = Field(
        default=None,
        description="One-letter VTEC significance such as W, A, or Y; requires phenomena.",
    )

    @model_validator(mode="after")
    def _well_formed(self) -> VtecEventsParams:
        if self.ugc is not None:
            self.ugc = self.ugc.upper()
            if not _UGC.fullmatch(self.ugc):
                raise ValueError(
                    "ugc must be a state's postal code, C or Z, and three digits, such as OKC113"
                )
        if (self.phenomena is None) is not (self.significance is None):
            raise ValueError("phenomena and significance must be given together, such as TO and W")
        if self.phenomena is not None and self.significance is not None:
            self.phenomena, self.significance = self.phenomena.upper(), self.significance.upper()
            if not _PHENOMENA.fullmatch(self.phenomena):
                raise ValueError("phenomena must be two letters, such as TO")
            if not _SIGNIFICANCE.fullmatch(self.significance):
                raise ValueError("significance must be one letter, such as W")
        return self


def _stamp(value: datetime) -> str:
    """A UTC instant as the service reads it, to the second."""
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class NwsVtecEvents(HttpProvider):
    """Events issued for one county or zone inside a window, as one CSV; keyed by place."""

    params_model = VtecEventsParams

    def list_assets(self, query: Query) -> list[Asset]:
        """The one CSV of events issued for the named county or UGC inside the window."""
        params = self.parse_params(query, VtecEventsParams)
        self.reject(
            query,
            "text",
            "variables",
            hint="the CSV columns are fixed; filter rows and columns locally",
        )
        place = self.place_of(query, hint="pass ugc")
        if place is not None and params.ugc is not None:
            raise QueryError(f"{self.dataset.id} was given a location and a ugc; pass one of them")
        if place is not None and place.county_fips is None:
            raise QueryError(
                f"{self.dataset.id} selects one county at a time, and {place.label} is a state; "
                "name a county with location, or pass ugc"
            )
        if place is not None:
            ugc = f"{place.state}C{place.county_fips}"
        elif params.ugc is not None:
            ugc = params.ugc
        else:
            raise QueryError(f"{self.dataset.id} requires a county location or a ugc")
        start, end = self.utc_window(query)
        filters = {"ugc": ugc, "sts": _stamp(start), "ets": _stamp(end + timedelta(seconds=1))}
        if params.phenomena is not None and params.significance is not None:
            filters.update(phenomena=params.phenomena, significance=params.significance)
        url = httpx.URL(SERVICE_URL, params={**filters, "fmt": "csv"})
        digest = hashlib.sha256(str(url).encode()).hexdigest()[:20]
        return [
            Asset(
                id=f"vtec_{ugc}_{start:%Y%m%d}_{end:%Y%m%d}_{digest}.csv",
                dataset_id=self.dataset.id,
                href=str(url),
                protocol=Protocol.HTTP,
                media_type="text/csv",
                time=TimeRange(start=start, end=end),
                bbox=query.bbox,
            )
        ]

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download the CSV as the service serves it."""
        return http.download(asset.href, dest, self._http())
