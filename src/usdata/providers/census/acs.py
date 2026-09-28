"""American Community Survey 5-year estimates from the Census Data API, which needs a free key.

The service answers one query per request with a JSON array of arrays: a header
row naming the columns, then one row per geography, every value a string. The
requested variables come first and the geography columns (``state``,
``county``) follow. Every data request carries a ``key`` query parameter, which
usdata reads from ``USDATA_CENSUS_KEY`` and adds only as each request is sent
(ADR 0039).

Selection (ADR 0045):

- ``vintage`` names the estimates by the last year of their five-year period, so
  2023 is 2019 through 2023. A time window is refused: a five-year estimate
  describes a period, and choosing one from a window would be a guess.
- The query's ``variables`` name one to fifty API variables, ``NAME``
  included, the service's limit per request. Margins of error and annotations
  are variables too, such as ``B01003_001M`` and ``B01003_001EA``.
- A ``location`` names one state or county. ``geography`` says what each row
  is: the place itself by default, or, for a state, every county in it. A box
  names no place and is refused.
- Connecticut's codes depend on the vintage: its eight counties through 2021,
  its nine planning regions from 2022. A place the vintage does not have is
  refused with the ones that it does.

The response is written as served. It carries no copy of the key and identical
requests return identical bytes, so there is nothing to canonicalize. The
service answers a geography it does not have with an empty ``204`` and a bad
key with a redirect; both are refused rather than written.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Annotated

import httpx
from pydantic import BaseModel, ConfigDict, Field

from usdata.models import Asset, Place, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.providers.base import QueryError
from usdata.providers.http import HttpProvider
from usdata.providers.params import choice, int_range
from usdata.query import legacy_counties, planning_regions

SERVICE_URL = "https://api.census.gov/data"
KEY = "USDATA_CENSUS_KEY"
FIRST_VINTAGE = 2009
"""The first ACS 5-year vintage the API lists, covering 2005 through 2009."""

REGIONS_FROM = 2022
"""The first vintage keyed by Connecticut's planning regions rather than its old counties."""

MAX_VARIABLES = 50
"""The most variables, ``NAME`` included, the service returns for one request."""

_VARIABLE = re.compile(r"[A-Z][A-Z0-9_]*")


class CensusError(QueryError):
    """The Census Data API refused the request and said why, or refused the key."""


class AcsParams(BaseModel):
    """Which estimates one ACS query names, and what each of its rows is."""

    model_config = ConfigDict(extra="forbid")

    vintage: Annotated[int, int_range(FIRST_VINTAGE, 9999)] = Field(
        description=(
            "Required last year of the five-year period, such as 2023 for 2019-2023; "
            "the estimates are selected by vintage, not by a date window."
        )
    )
    geography: Annotated[str, choice("state", "county")] | None = Field(
        default=None,
        description=(
            "What each row is: state or county. Defaults to the kind of place the location "
            "names; county with a state location gives every county in it."
        ),
    )


def _variables(names: list[str], dataset_id: str) -> list[str]:
    """The query's variables upper-cased, repeats dropped, in the order given."""
    ordered = list(dict.fromkeys(name.strip().upper() for name in names))
    if not ordered or not all(ordered):
        raise QueryError(
            f"{dataset_id} needs variables naming the estimates to return, such as "
            "NAME,B01003_001E,B01003_001M"
        )
    if bad := [name for name in ordered if not _VARIABLE.fullmatch(name)]:
        raise QueryError(f"{dataset_id} variable {bad[0]!r} is not a Census API variable name")
    if len(ordered) > MAX_VARIABLES:
        raise QueryError(
            f"{dataset_id} was given {len(ordered)} variables; the service returns at most "
            f"{MAX_VARIABLES} per request, NAME included, so split them across manifest sources"
        )
    return ordered


def _labels(places: tuple[Place, ...]) -> str:
    return "; ".join(place.label for place in places)


class Acs5Year(HttpProvider):
    """ACS 5-year detailed-table estimates for one vintage, variable list, and place."""

    params_model = AcsParams

    def list_assets(self, query: Query) -> list[Asset]:
        """One JSON asset for the query's vintage, variables, and place; nothing is requested."""
        params = self.parse_params(query, AcsParams)
        self.reject(
            query,
            "text",
            "time",
            hint="choose the five-year period with vintage, such as vintage=2023 for 2019-2023",
        )
        variables = _variables(query.variables, self.dataset.id)
        place = self.place_of(query, hint="the estimates are keyed by state and county")
        if place is None:
            raise QueryError(f"{self.dataset.id} needs a location naming a state or county")
        self._check_connecticut(place, params.vintage)
        geography = params.geography or place.kind
        if geography == "state" and place.kind == "county":
            raise QueryError(
                f"{self.dataset.id} geography=state needs a state location, not {place.label}"
            )
        selection: dict[str, str]
        if place.kind == "state" and geography == "state":
            selection, label = {"for": f"state:{place.state_fips}"}, place.geoid
        elif place.kind == "state":
            selection = {"for": "county:*", "in": f"state:{place.state_fips}"}
            label = f"{place.geoid}-counties"
        else:
            selection = {"for": f"county:{place.county_fips}", "in": f"state:{place.state_fips}"}
            label = place.geoid
        url = httpx.URL(
            f"{SERVICE_URL}/{params.vintage}/acs/acs5",
            params={"get": ",".join(variables), **selection},
        )
        digest = hashlib.sha256(",".join(variables).encode()).hexdigest()[:12]
        first = params.vintage - 4
        return [
            Asset(
                id=f"acs5_{params.vintage}_{label}_{digest}.json",
                dataset_id=self.dataset.id,
                href=str(url),
                protocol=Protocol.HTTP,
                media_type="application/json",
                time=TimeRange(
                    start=datetime(first, 1, 1, tzinfo=UTC),
                    end=datetime.combine(datetime(params.vintage, 12, 31), time.max, UTC),
                ),
                bbox=query.bbox,
                properties={"vintage": str(params.vintage), "period": f"{first}-{params.vintage}"},
            )
        ]

    def _check_connecticut(self, place: Place, vintage: int) -> None:
        """Refuse a Connecticut place the vintage's geography does not have (ADR 0045)."""
        if vintage < REGIONS_FROM and (counties := legacy_counties(place)):
            raise QueryError(
                f"{self.dataset.id} vintage {vintage} keys Connecticut by its eight counties "
                f"before 2022, and {place.label} is a planning region that replaced them; name "
                f"a county it overlaps with location: {_labels(counties)}"
            )
        if vintage >= REGIONS_FROM and (regions := planning_regions(place)):
            raise QueryError(
                f"{self.dataset.id} vintage {vintage} keys Connecticut by the planning regions "
                f"that replaced its counties in 2022, and {place.label} is one of those "
                f"counties; name a region it overlaps with location: {_labels(regions)}"
            )

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Request the estimates with this adapter's key and write the response as served."""
        vintage = asset.properties.get("vintage", "?")
        with self.redacted_errors():
            keyed = httpx.URL(asset.href).copy_merge_params({"key": self.credentials[KEY]})
            try:
                # A bad key is a redirect to an explanation page, which is refused, not followed.
                response = http.get(keyed, self._http(), follow_redirects=False)
            except httpx.HTTPStatusError as error:
                # Any other status, such as a 503, stays an upstream failure.
                if (refusal := _refusal(error.response, vintage)) is None:
                    raise
                raise refusal from error
            if response.status_code == 204:
                raise CensusError(
                    f"the Census Data API has no rows for {_where(asset.href)} in ACS 5-year "
                    f"vintage {vintage}; the place's code may differ in that vintage"
                )
            _check_table(response)
        dest.write_bytes(response.content)
        return dest


def _refusal(response: httpx.Response, vintage: str) -> CensusError | None:
    """The service's refusal as an error that says why, or None for an upstream failure."""
    status = response.status_code
    location = response.headers.get("location", "")
    if response.is_redirect and "invalid_key" in location:
        return CensusError(
            f"the Census Data API refused the key in {KEY} as invalid; check it, and that the "
            "activation link in the signup email was followed"
        )
    if response.is_redirect and "missing_key" in location:
        return CensusError(f"the Census Data API answered as if no key was sent; check {KEY}")
    if status == 400 and response.headers.get("content-type", "").startswith("text/plain"):
        reason = response.text.strip().removeprefix("error:").strip()
        return CensusError(f"the Census Data API refused the request: {reason}")
    if status == 404:
        return CensusError(f"the Census Data API publishes no ACS 5-year vintage {vintage}")
    return None


def _where(href: str) -> str:
    """The geography a request names, as the service's ``for`` and ``in`` spell it."""
    params = httpx.URL(href).params
    place = params.get("for", "")
    return f"{place} in {params['in']}" if "in" in params else place


def _check_table(response: httpx.Response) -> None:
    """Raise unless the body is the array of rows, header first, that the service promises."""
    try:
        body = json.loads(response.content)
    except ValueError:
        body = None
    if not (
        isinstance(body, list)
        and body
        and all(isinstance(row, list) and len(row) == len(body[0]) for row in body)
    ):
        raise httpx.DecodingError(
            "the Census Data API answered with something other than a table of rows",
            request=response.request,
        )
