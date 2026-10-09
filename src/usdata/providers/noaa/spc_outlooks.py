"""SPC convective and fire weather outlooks from IEM's archive, as zipped shapefiles.

The Iowa Environmental Mesonet archives every Storm Prediction Center outlook
it has parsed, convective from 1987 and fire weather later, and serves those
issued in a UTC window as one zipped shapefile: one row per outlook area, with
the outlook's day (1 to 8), its valid period, the product's issuance time, the
threshold and its category, and the issuance cycle. The same service also
serves WPC excessive rainfall outlooks, which are not SPC products and are not
part of this dataset.

Four things about the service shape the queries (ADR 0053):

- The window selects outlooks by ``PRODISS``, the time SPC issued the product,
  and not by the period the outlook is valid for. That is what a forecast made
  before a moment could have used. ``ets`` is exclusive, so the end sent is
  one second later.
- Every issuance is returned, corrections included. ``CYCLE`` names the one
  IEM takes as canonical for each issuance hour; the others carry ``-1``.
- A window with no outlooks is answered with a line of plain text rather than
  an empty shapefile, so ``fetch`` writes a zip with no members for it. An
  outlook that drew no area, as Days 4 to 8 often do, is still a row: a null
  shape with an empty threshold and category.
- The window is split at UTC month boundaries, one zip per month, which keeps
  every request under the service's cap of ten outlook years, and each zip is
  stamped with the time it was built, so ``fetch`` writes a canonical form
  (``iem_gis``).

There is no bundled shapefile reader; the zip opens with geopandas or pyshp.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Annotated

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.providers.noaa.iem_gis import IemShapefiles, last_second, months, stamp
from usdata.providers.params import StrList, choice, int_list

SERVICE_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/gis/outlooks.py"
OUTLOOK_TYPES = {"convective": "C", "fire": "F"}
"""Each outlook this dataset reads and the code the service names it by."""

GEOMETRIES = {"cake_layer": "geom_layers", "cookie_cutter": "geom"}
"""Each geometry form and the value the service's ``geom`` parameter takes for it."""


class SpcOutlooksParams(BaseModel):
    """What narrows an outlook query beyond its window."""

    model_config = ConfigDict(extra="forbid")

    outlooks: StrList = Field(
        default=["convective"],
        description="Outlook type(s): convective (the default), fire, or both.",
    )
    days: Annotated[list[int], int_list(1, 8)] | None = Field(
        default=None,
        description="Outlook day(s) from 1 to 8; every day by default.",
    )
    geometry: Annotated[str, choice(*GEOMETRIES)] = Field(
        default="cake_layer",
        description=(
            "cake_layer (the default), where each threshold's area includes the higher ones "
            "inside it, or cookie_cutter, where each area excludes them."
        ),
    )

    @model_validator(mode="after")
    def _well_formed(self) -> SpcOutlooksParams:
        self.outlooks = list(dict.fromkeys(value.lower() for value in self.outlooks))
        if unknown := [value for value in self.outlooks if value not in OUTLOOK_TYPES]:
            raise ValueError(f"outlooks must be convective or fire, not {', '.join(unknown)}")
        return self


class SpcOutlooks(IemShapefiles):
    """Outlook areas issued inside a window, one zip per UTC month."""

    params_model = SpcOutlooksParams
    no_results = b"ERROR: no results found"

    def list_assets(self, query: Query) -> list[Asset]:
        """One zip per UTC month the window touches; nothing is requested."""
        params = self.parse_params(query, SpcOutlooksParams)
        self.reject(
            query,
            "text",
            "bbox",
            "variables",
            hint="outlooks cover the nation; clip their areas locally",
        )
        filters = {
            "type": ",".join(OUTLOOK_TYPES[value] for value in params.outlooks),
            "geom": GEOMETRIES[params.geometry],
        }
        if params.days is not None:
            filters["d"] = ",".join(str(day) for day in sorted(params.days))
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
                    id=f"outlooks_{first:%Y%m%d}_{last:%Y%m%d}_{digest}.zip",
                    dataset_id=self.dataset.id,
                    href=str(url),
                    protocol=Protocol.HTTP,
                    media_type="application/zip",
                    time=TimeRange(start=first, end=last),
                )
            )
        return assets
