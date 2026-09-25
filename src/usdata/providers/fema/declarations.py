"""FEMA Disaster Declarations Summaries from the OpenFEMA v2 API.

One anonymous endpoint answers an OData-style ``$filter`` and serves the result
as CSV: one row per declaration and designated area, with the incident type and
period, the programs declared, and the state and county FIPS codes. The rows
carry no coordinates, so this is a source keyed by place: a ``location`` selects
its state or county exactly, and a bare ``bbox`` or ``lat``/``lon`` is refused
(ADR 0034).

Three things about the service shape the queries, each learned by getting it
wrong first (ADR 0035):

- A timestamp in a ``$filter`` must be a date alone. The server compares a full
  timestamp against the still-percent-encoded literal, so it matches nothing.
- The window that matters is the incident period, not the declaration date. A
  declaration is often made days after its incident began, and is sometimes
  made before it ended, so a window selects the declarations whose incident
  period overlaps it, inclusive at both ends.
- A missing ``incidentEndDate`` does not mean recent. Several hundred rows have
  none, most of them fire declarations years old that were never closed, which
  would overlap every later window forever. They are left out unless
  ``include_open`` asks for them.

County code ``000`` marks a designated area that is not a county: a statewide
designation, or a tribal area. A county selection also returns its state's
``Statewide`` rows, which do cover that county, and no tribal area, which is
not one; a state selection returns them all.

Connecticut's rows carry the eight counties it had before 2022, not the
planning regions that replaced them as county equivalents. A planning-region
location is refused with the counties it overlaps, which the place table also
holds.

Listing asks for the count first and makes one asset per page under a fixed
order, so page membership is stable. The dataset is rebuilt every twenty minutes
and rows are revised as incidents close, so a pinned page can change bytes;
that is drift, not an error in the adapter.
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.providers.base import QueryError
from usdata.providers.http import HttpProvider
from usdata.providers.params import OptionalUpperStrList, StrList, flag

SERVICE_URL = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"
ENTITY = "DisasterDeclarationsSummaries"
PAGE_SIZE = 10000
"""Rows per asset. The service returned more when asked, so this is a choice, not its cap."""

ORDER = "declarationDate,id"
"""A total order, so consecutive pages are disjoint; row ids survive the dataset's rebuilds."""

STATEWIDE = "Statewide"
"""The ``designatedArea`` of a declaration covering every county of its state."""

DECLARATION_TYPES = ("DR", "EM", "FM")
_STATE = re.compile(r"[A-Za-z]{2}")
_FIPS = re.compile(r"\d{5}")
_INCIDENT = re.compile(r"[A-Za-z][A-Za-z /()-]*")


class DeclarationsParams(BaseModel):
    """What one declarations query names beyond its window; the place comes from the query."""

    model_config = ConfigDict(extra="forbid")

    state: str | None = Field(
        default=None, description="Two-letter postal code of one state or territory, such as OK."
    )
    fips: str | None = Field(
        default=None,
        description=(
            "Five-digit FIPS code of one county, such as 40113; also returns its state's "
            "Statewide designations."
        ),
    )
    incident_type: StrList | None = Field(
        default=None,
        description="Incident type(s) as FEMA writes them, such as Tornado or Severe Storm.",
    )
    declaration_type: OptionalUpperStrList = Field(
        default=None,
        description="Declaration type(s): DR (major disaster), EM (emergency), FM (fire).",
    )
    include_open: Annotated[bool, flag()] = Field(
        default=False,
        description=(
            "Also return incidents with no end date, most of them old fire declarations "
            "that were never closed; false by default."
        ),
    )

    @model_validator(mode="after")
    def _well_formed(self) -> DeclarationsParams:
        if self.state is not None and self.fips is not None:
            raise ValueError("pass state or fips, not both; a county code already names its state")
        if self.state is not None:
            if not _STATE.fullmatch(self.state):
                raise ValueError("state must be a two-letter postal code such as OK")
            self.state = self.state.upper()
        if self.fips is not None and not _FIPS.fullmatch(self.fips):
            raise ValueError("fips must be a five-digit county FIPS code such as 40113")
        for value in self.declaration_type or []:
            if value not in DECLARATION_TYPES:
                raise ValueError(f"declaration_type {value!r} must be DR, EM, or FM")
        for value in self.incident_type or []:
            if not _INCIDENT.fullmatch(value):
                raise ValueError(f"incident_type {value!r} must be letters, spaces, and / ( ) -")
        return self


def _county(state_fips: str, county_fips: str) -> str:
    """One county, and the statewide designations of its state, which cover it."""
    return (
        f"fipsStateCode eq '{state_fips}' and "
        f"(fipsCountyCode eq '{county_fips}' or designatedArea eq '{STATEWIDE}')"
    )


def _any_of(field: str, values: list[str]) -> str:
    """``field`` equal to one of ``values``, parenthesized when there is more than one."""
    terms = " or ".join(f"{field} eq '{value}'" for value in values)
    return f"({terms})" if len(values) > 1 else terms


class DisasterDeclarations(HttpProvider):
    """Declarations whose incident period overlaps the window, as CSV pages; keyed by place."""

    params_model = DeclarationsParams

    def list_assets(self, query: Query) -> list[Asset]:
        """One CSV asset per page of declarations matching the window, place, and filters."""
        params = self.parse_params(query, DeclarationsParams)
        self.reject(
            query,
            "text",
            "variables",
            hint="the CSV columns are fixed; filter rows and columns locally",
        )
        place = self.place_of(query, hint="pass state or fips")
        if place is not None and (params.state is not None or params.fips is not None):
            raise QueryError(
                f"{self.dataset.id} was given a location and a state or fips; pass one of them"
            )
        self.refuse_planning_region(place)
        start, end = self.utc_window(query)
        terms = [self._period(start, end, include_open=params.include_open)]
        if place is not None and place.county_fips is not None:
            terms.append(_county(place.state_fips, place.county_fips))
        elif place is not None:
            terms.append(f"fipsStateCode eq '{place.state_fips}'")
        elif params.fips is not None:
            terms.append(_county(params.fips[:2], params.fips[2:]))
        elif params.state is not None:
            terms.append(f"state eq '{params.state}'")
        if params.incident_type:
            terms.append(_any_of("incidentType", params.incident_type))
        if params.declaration_type:
            terms.append(_any_of("declarationType", params.declaration_type))
        where = " and ".join(terms)
        window = TimeRange(start=start, end=end)
        assets: list[Asset] = []
        for page in range(math.ceil(self._count(where) / PAGE_SIZE)):
            url = httpx.URL(
                SERVICE_URL,
                params={
                    "$filter": where,
                    "$orderby": ORDER,
                    "$top": str(PAGE_SIZE),
                    "$skip": str(page * PAGE_SIZE),
                    "$format": "csv",
                },
            )
            digest = hashlib.sha256(str(url).encode()).hexdigest()[:20]
            assets.append(
                Asset(
                    id=f"declarations_{start:%Y%m%d}_{end:%Y%m%d}_{digest}.csv",
                    dataset_id=self.dataset.id,
                    href=str(url),
                    protocol=Protocol.HTTP,
                    media_type="text/csv",
                    time=window,
                    bbox=query.bbox,
                )
            )
        return assets

    @staticmethod
    def _period(start: datetime, end: datetime, *, include_open: bool) -> str:
        """Incident periods overlapping the window, by date alone and inclusive at both ends."""
        ended = f"incidentEndDate ge '{start:%Y-%m-%d}'"
        if include_open:
            ended = f"({ended} or incidentEndDate eq null)"
        return f"incidentBeginDate le '{end:%Y-%m-%d}' and {ended}"

    def _count(self, where: str) -> int:
        """How many rows the filter matches, from the service's own inline count."""
        response = http.get(
            SERVICE_URL,
            self._http(),
            params={"$filter": where, "$inlinecount": "allpages", "$top": "1", "$select": "id"},
        )
        try:
            count = response.json()["metadata"]["count"]
        except (ValueError, KeyError, TypeError):
            count = None
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise httpx.DecodingError(
                f"OpenFEMA did not return a count: {response.text[:200]!r}",
                request=response.request,
            )
        return count

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download one CSV page as the service serves it."""
        return http.download(asset.href, dest, self._http())
