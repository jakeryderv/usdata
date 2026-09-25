"""EPA Air Quality System daily summaries from the AQS Data API, which needs a free key.

The service answers one request per selection with JSON: a ``Header`` saying how
the request went and a ``Data`` list with one element per monitor, local day,
and pollutant standard. Every request carries an ``email`` and ``key`` as query
parameters, which usdata reads from ``USDATA_AQS_EMAIL`` and ``USDATA_AQS_KEY``
and adds only as each request is sent (ADR 0039).

Selection (ADR 0040):

- ``parameters`` names one to five AQS parameter codes, the service's limit, such
  as 88101 for PM2.5 and 44201 for ozone. The columns are fixed, so a
  ``variables`` filter is refused.
- A place comes from exactly one of: ``sites`` (AQS site ids, ``SS-CCC-NNNN``),
  a ``location`` naming a state or county, which selects it exactly, or a bare
  ``bbox`` or ``lat``/``lon``, which selects the monitors inside the box.
- The window's UTC calendar dates select local days, inclusive. The service
  refuses a request spanning two calendar years, so each year becomes its own
  asset, and each site its own asset too.

What is written is not the bytes as sent. The response header echoes the whole
request URL, key included, and its ``request_time`` and the order of the rows
change between identical requests, so ``fetch`` writes a canonical form: the
header without those two fields, the rows sorted, and the JSON serialized with
sorted keys and fixed separators. ``Provider.transformations`` says so in every
provenance sidecar.

EPA asks callers to send one request at a time, at most ten a minute, with a
pause between them, and will disable an account that does not. Requests from
this module, transport retries included, are therefore spaced at least
``MIN_INTERVAL`` apart, across every adapter instance in the process. Responses
are slow, a minute or more for a county-month, so the read timeout is long.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import UTC, date, datetime, time
from pathlib import Path
from time import monotonic
from typing import Annotated, Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from usdata.models import Asset, BBox, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.providers.base import QueryError
from usdata.providers.http import HttpProvider
from usdata.providers.params import StrList, int_list

SERVICE_URL = "https://aqs.epa.gov/data/api/dailyData/"
EMAIL = "USDATA_AQS_EMAIL"
KEY = "USDATA_AQS_KEY"
MAX_PARAMETERS = 5
"""The most parameter codes the service accepts in one request."""

MIN_INTERVAL = 6.0
"""Seconds between the starts of two requests: EPA asks for a pause and at most ten a minute."""

TIMEOUT = httpx.Timeout(10.0, read=600.0)
"""A county-month took about two minutes to answer when probed; a state-year takes longer."""

SUCCESS = "Success"
NO_DATA = "No data matched your selection"
"""The two header statuses that are answers rather than failures."""

ROW_ORDER = (
    "state_code",
    "county_code",
    "site_number",
    "parameter_code",
    "poc",
    "date_local",
    "sample_duration_code",
    "pollutant_standard",
    "method_code",
    "event_type",
)
"""The columns rows are sorted by; the whole row, serialized, breaks any remaining tie."""

ECHOED = ("url", "request_time")
"""Header fields that describe the request rather than the data, dropped from what is written."""

_SITE = re.compile(r"(\d{2})-(\d{3})-(\d{4})")


class AqsError(QueryError):
    """The service refused the request and said why, in its response header."""


class AqsDailyParams(BaseModel):
    """Which pollutants one AQS query names, and which sites unless the query names a place."""

    model_config = ConfigDict(extra="forbid")

    parameters: Annotated[list[int], int_list(10000, 99999)] = Field(
        description=(
            "Required AQS parameter code(s), one to five, such as 88101 (PM2.5) or 44201 (ozone)."
        )
    )
    sites: StrList | None = Field(
        default=None,
        description="AQS site id(s) as state-county-site, such as 36-081-0124; or use a location.",
    )

    @model_validator(mode="after")
    def _within_limits(self) -> AqsDailyParams:
        if len(self.parameters) > MAX_PARAMETERS:
            raise ValueError(
                f"parameters names {len(self.parameters)} codes; the service takes at most "
                f"{MAX_PARAMETERS} per request, so split them across manifest sources"
            )
        for site in self.sites or []:
            if not _SITE.fullmatch(site):
                raise ValueError(
                    f"sites entry {site!r} must be state-county-site, such as 36-081-0124"
                )
        return self


def _site_filters(site: str) -> dict[str, str]:
    """The state, county, and site codes of one validated ``SS-CCC-NNNN`` id."""
    state, county, number = site.split("-")
    return {"state": state, "county": county, "site": number}


def _box_label(box: BBox) -> str:
    """A short stable label for a box, which has no id of its own."""
    text = f"{box.south:.6f},{box.north:.6f},{box.west:.6f},{box.east:.6f}"
    return "box-" + hashlib.sha256(text.encode()).hexdigest()[:12]


def _degrees(value: float) -> str:
    """A box edge as sent: the six decimals ``_box_label`` hashes, without trailing zeros.

    Two boxes then share a request URL exactly when they share a label, and an
    edge given to six decimals or fewer is sent as given.
    """
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _row_key(row: dict[str, Any]) -> tuple[str, ...]:
    """Where a row sorts: its identifying columns as text, then the whole row."""
    return (
        *("" if row.get(name) is None else str(row.get(name)) for name in ROW_ORDER),
        json.dumps(row, sort_keys=True),
    )


def _header(body: object) -> list[dict[str, Any]]:
    """The entries of a response's ``Header``, or none when it has no such list."""
    header = body.get("Header") if isinstance(body, dict) else None
    return (
        [entry for entry in header if isinstance(entry, dict)] if isinstance(header, list) else []
    )


def _status(body: object) -> object:
    """The status a response header gives, or None when there is no header saying one."""
    entries = _header(body)
    return entries[0].get("status") if entries else None


def _failure(body: object) -> str | None:
    """The reason a response header gives for refusing a request, or None if it gives none.

    A body with no header status, such as an HTML maintenance page, gives no
    reason: that is the service failing, not refusing, and stays an HTTP error.
    """
    if _status(body) in (None, SUCCESS, NO_DATA):
        return None
    reasons = [
        "; ".join(map(str, entry["error"]))
        if isinstance(entry.get("error"), list)
        else str(entry.get("error") or entry.get("status"))
        for entry in _header(body)
    ]
    return "; ".join(reasons)


def canonical(body: dict[str, Any]) -> bytes:
    """The response as usdata stores it: no echoed request, rows in a fixed order.

    Raises:
        AqsError: The header reports a failure rather than data or an empty selection.
        httpx.DecodingError: There is no header status to say how the request went.
    """
    if (reason := _failure(body)) is not None:
        raise AqsError(f"AQS refused the request: {reason}")
    if _status(body) is None:
        raise httpx.DecodingError("AQS answered without a Header status")
    header = [
        {name: value for name, value in entry.items() if name not in ECHOED}
        for entry in _header(body)
    ]
    rows = body.get("Data") or []
    ordered = sorted(rows, key=_row_key) if isinstance(rows, list) else rows
    return json.dumps(
        {"Header": header, "Data": ordered}, sort_keys=True, separators=(",", ":")
    ).encode()


def _json(response: httpx.Response) -> object:
    """The response body as JSON, or None when it is not JSON."""
    try:
        return response.json()
    except ValueError:
        return None


class _Pace:
    """Space the starts of requests to one host at least ``MIN_INTERVAL`` apart, process-wide."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last: float | None = None

    def wait(self) -> None:
        with self._lock:
            if self._last is not None:
                remaining = MIN_INTERVAL - (monotonic() - self._last)
                if remaining > 0:
                    http.sleep(remaining)
            self._last = monotonic()


PACE = _Pace()


class AqsDaily(HttpProvider):
    """Daily summaries for named pollutants over sites, a place, or a box, one asset per year."""

    params_model = AqsDailyParams
    transformations = (
        "aqs canonical json: Header url and request_time removed; Data sorted by site, "
        "parameter, poc, local date, duration, standard, method, and event type",
    )

    def list_assets(self, query: Query) -> list[Asset]:
        """One JSON asset per selection and calendar year of the window; nothing is requested."""
        params = self.parse_params(query, AqsDailyParams)
        self.reject(
            query,
            "text",
            "variables",
            hint="choose pollutants with parameters; the columns are fixed",
        )
        if params.sites and query.bbox is not None:
            raise QueryError(
                f"{self.dataset.id} was given sites and a location or bbox; pass one of them"
            )
        start, end = self.utc_window(query)
        first, last = start.date(), end.date()
        selections = self._selections(query, params)
        codes = [str(code) for code in params.parameters]
        assets: list[Asset] = []
        for year in range(first.year, last.year + 1):
            bdate, edate = max(first, date(year, 1, 1)), min(last, date(year, 12, 31))
            for label, service, filters in selections:
                url = httpx.URL(
                    SERVICE_URL + service,
                    params={
                        "param": ",".join(codes),
                        "bdate": f"{bdate:%Y%m%d}",
                        "edate": f"{edate:%Y%m%d}",
                        **filters,
                    },
                )
                assets.append(
                    Asset(
                        id=f"aqs-daily_{label}_{'-'.join(codes)}_{bdate:%Y%m%d}_{edate:%Y%m%d}.json",
                        dataset_id=self.dataset.id,
                        href=str(url),
                        protocol=Protocol.HTTP,
                        media_type="application/json",
                        time=TimeRange(
                            start=datetime.combine(bdate, time.min, UTC),
                            end=datetime.combine(edate, time.max, UTC),
                        ),
                        bbox=query.bbox,
                    )
                )
        return assets

    def _selections(
        self, query: Query, params: AqsDailyParams
    ) -> list[tuple[str, str, dict[str, str]]]:
        """Each request's label, service path, and place filters, in a stable order."""
        if params.sites:
            return [(f"site-{site}", "bySite", _site_filters(site)) for site in params.sites]
        place = query.place
        if place is not None and place.county_fips is not None:
            filters = {"state": place.state_fips, "county": place.county_fips}
            return [(f"county-{place.geoid}", "byCounty", filters)]
        if place is not None:
            return [(f"state-{place.state_fips}", "byState", {"state": place.state_fips})]
        if query.bbox is not None:
            box = query.bbox
            filters = {
                "minlat": _degrees(box.south),
                "maxlat": _degrees(box.north),
                "minlon": _degrees(box.west),
                "maxlon": _degrees(box.east),
            }
            return [(_box_label(box), "byBox", filters)]
        raise QueryError(
            f"{self.dataset.id} needs a place: sites, or a location or bbox to select monitors"
        )

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Request the selection with this adapter's key and write the canonical JSON."""
        with self.redacted_errors():
            try:
                # httpx replaces a URL's query when given params, so merge the keys into it.
                keyed = httpx.URL(asset.href).copy_merge_params(
                    {"email": self.credentials[EMAIL], "key": self.credentials[KEY]}
                )
                # A transport retry is a request to EPA too, so every attempt is paced.
                response = http.get(keyed, self._http(), before_attempt=PACE.wait, timeout=TIMEOUT)
            except httpx.HTTPStatusError as error:
                # A refusal comes as a 4xx whose JSON header says why; keep that reason.
                # Any other error, such as a 503 maintenance page, stays an upstream failure.
                if (reason := _failure(_json(error.response))) is None:
                    raise
                status = error.response.status_code
                if "key" in reason.lower():
                    reason = f"{reason} Check {EMAIL} and {KEY}."
                raise AqsError(f"AQS refused the request ({status}): {reason}") from error
            body = _json(response)
            if not isinstance(body, dict):
                raise httpx.DecodingError(
                    "AQS answered with something other than a JSON object",
                    request=response.request,
                )
            data = canonical(body)
        dest.write_bytes(data)
        return dest
