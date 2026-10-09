"""NWS watch, warning, and advisory geometries from IEM's archive, as zipped shapefiles.

The Iowa Environmental Mesonet keeps the maintained archive of National Weather
Service VTEC products and serves it, for a UTC window, as one zip holding a
shapefile and the same attributes as CSV. Every product is there: storm-based
warning polygons (``GTYPE`` ``P``) from 2002, and the counties and forecast
zones each watch, warning, and advisory was issued for (``GTYPE`` ``C``) from
1986 for tornado, severe thunderstorm, flash flood, and marine warnings and
from November 2005 for the rest. The official NWS API keeps no archive.

Four things about the service shape the queries (ADR 0053):

- The window selects rows by ``ISSUED``, the event's start as last updated,
  and not by when it was in effect or by when its first product was sent. A
  watch issued before the window and still running through it is not
  returned. For tornado and severe thunderstorm warnings ``ISSUED`` is the
  issuing product's time; for a product that begins in the future, such as a
  winter storm watch, ``INIT_ISS`` holds when it was sent.
- ``ets`` is exclusive where a usdata window's end is inclusive, so the end
  sent is one second later, and the window is split at UTC month boundaries,
  one zip per month, which keeps every request under the service's one-year
  cap on an unnarrowed download.
- A place is a state or a set of offices, not a box: the rows of county and
  zone products carry codes, and the service filters by ``states`` or by
  ``wfo``. A county is refused, naming ``noaa:nws-vtec-events``, which reads
  one county's events.
- Each zip is built on request and stamped with the time it was built, so
  ``fetch`` writes a canonical form (``iem_gis``).

There is no bundled shapefile reader; the zip opens with geopandas or pyshp.
"""

from __future__ import annotations

import hashlib
import re
from datetime import timedelta
from typing import Annotated

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.providers.base import QueryError
from usdata.providers.noaa.iem_gis import IemShapefiles, last_second, months, stamp
from usdata.providers.params import OptionalUpperStrList, flag

SERVICE_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/gis/watchwarn.py"
_EVENT = re.compile(r"([A-Z]{2})\.([A-Z])")
_OFFICE = re.compile(r"[A-Z]{3,4}")


class NwsWarningsParams(BaseModel):
    """What narrows a warnings query beyond its window and state."""

    model_config = ConfigDict(extra="forbid")

    events: OptionalUpperStrList = Field(
        default=None,
        description=(
            "VTEC phenomena and significance pairs such as TO.W, SV.W, or TO.A; every "
            "watch, warning, and advisory by default."
        ),
    )
    wfo: OptionalUpperStrList = Field(
        default=None,
        description=(
            "Issuing office code(s) such as OUN or TSA, in place of a state location; "
            "every office by default."
        ),
    )
    storm_based: Annotated[bool, flag()] = Field(
        default=False,
        description=(
            "Keep only storm-based warning polygons (GTYPE P), dropping county and zone "
            "rows; false by default."
        ),
    )
    followups: Annotated[bool, flag()] = Field(
        default=False,
        description=(
            "Add the polygons of follow-up statements issued after a warning, each its own "
            "row; only the issuance polygon by default."
        ),
    )

    @model_validator(mode="after")
    def _well_formed(self) -> NwsWarningsParams:
        for event in self.events or ():
            if not _EVENT.fullmatch(event):
                raise ValueError("events must be phenomena, a dot, and significance, such as TO.W")
        for office in self.wfo or ():
            if not _OFFICE.fullmatch(office):
                raise ValueError("wfo must be three or four letters, such as OUN")
        return self


class NwsWarnings(IemShapefiles):
    """Watch, warning, and advisory rows issued inside a window, one zip per UTC month."""

    params_model = NwsWarningsParams

    def list_assets(self, query: Query) -> list[Asset]:
        """One zip per UTC month the window touches; nothing is requested."""
        params = self.parse_params(query, NwsWarningsParams)
        self.reject(
            query,
            "text",
            "variables",
            hint="the shapefile's columns are fixed; filter rows and columns locally",
        )
        place = self.place_of(query, hint="pass wfo")
        if place is not None and params.wfo is not None:
            raise QueryError(f"{self.dataset.id} was given a location and wfo; pass one of them")
        if place is not None and place.county_fips is not None:
            raise QueryError(
                f"{self.dataset.id} selects by state or office, and {place.label} is a county; "
                f"name its state with location, or read one county's events from "
                f"noaa:nws-vtec-events"
            )
        filters: dict[str, str] = {"accept": "shapefile"}
        if place is not None:
            filters.update(location_group="states", states=place.state)
        elif params.wfo is not None:
            filters.update(location_group="wfo", wfo=",".join(params.wfo))
        if params.events is not None:
            pairs = [_EVENT.fullmatch(event) for event in params.events]
            filters.update(
                limitps="1",
                phenomena=",".join(pair.group(1) for pair in pairs if pair),
                significance=",".join(pair.group(2) for pair in pairs if pair),
            )
        if params.storm_based:
            filters["limit1"] = "1"
        if params.followups:
            filters["addsvs"] = "1"
        start, end = self.utc_window(query)
        assets = []
        for first, stop in months(start, end + timedelta(seconds=1)):
            url = httpx.URL(
                SERVICE_URL, params={**filters, "sts": stamp(first), "ets": stamp(stop)}
            )
            digest = hashlib.sha256(str(url).encode()).hexdigest()[:20]
            last = last_second(stop)
            assets.append(
                Asset(
                    id=f"wwa_{first:%Y%m%d}_{last:%Y%m%d}_{digest}.zip",
                    dataset_id=self.dataset.id,
                    href=str(url),
                    protocol=Protocol.HTTP,
                    media_type="application/zip",
                    time=TimeRange(start=first, end=last),
                    bbox=query.bbox,
                )
            )
        return assets
