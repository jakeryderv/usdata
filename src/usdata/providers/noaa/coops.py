"""CO-OPS observed water levels and tide predictions as raw CSV.

Both datasets share one station model: one seven-digit ``station``, an explicit
``datum``, optional ``units`` (metric or english), and both timestamps at minute
precision, requested in UTC; a bare end date means 23:59 on that day.
Observations span at most 28 days; predictions
span at most a year on any ``interval`` (six-minute by default, another minute
step, hourly, or high/low), within NOAA's own limits.
"""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, ClassVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from usdata._files import staged_path
from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.providers.base import QueryError
from usdata.providers.http import HttpProvider
from usdata.providers.params import choice
from usdata.query import LAST_INSTANT

DATA_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
DATUMS = {"CRD", "IGLD", "LWD", "MHHW", "MHW", "MTL", "MSL", "MLW", "MLLW", "NAVD", "STND"}
MAX_INTERVAL = timedelta(days=28)
MAX_PREDICTION_INTERVAL = timedelta(days=366)
INTERVALS = ("1", "5", "6", "10", "15", "30", "60", "h", "hilo")
OBSERVATION_COLUMNS = {
    "Date Time",
    "Water Level",
    "Sigma",
    "O or I (for verified)",
    "F",
    "R",
    "L",
    "Quality",
}
PREDICTION_COLUMNS = {"Date Time", "Prediction"}


def _rows(path: Path, asset: Asset, required: set[str]) -> Iterator[dict[str, str]]:
    """Yield stripped CSV rows, rejecting error documents and malformed responses."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        records = csv.reader(stream, strict=True)
        columns = [name.strip() for name in next(records, [])]
        if (
            any(not name for name in columns)
            or len(set(columns)) != len(columns)
            or not required.issubset(columns)
        ):
            raise ValueError("missing expected CSV columns")
        for values in records:
            if values and values[0].startswith("Error:"):
                raise ValueError(values[0][:512])
            if len(values) != len(columns):
                raise ValueError("CSV row does not match the header")
            row = {name: value.strip() for name, value in zip(columns, values, strict=True)}
            when = datetime.strptime(row["Date Time"], "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
            if asset.time is not None and not asset.time.overlaps(TimeRange(start=when, end=when)):
                raise ValueError("record lies outside the requested interval")
            yield row


def _validate_observations(path: Path, asset: Asset) -> None:
    count = 0
    for row in _rows(path, asset, OBSERVATION_COLUMNS):
        if row["Quality"] not in {"p", "v"}:
            raise ValueError("unrecognized observation quality")
        for field in ("Water Level", "Sigma"):
            if row[field]:
                float(row[field])
        count += 1
    if not count:
        raise ValueError("no water-level observations returned")


def _validate_predictions(path: Path, asset: Asset, interval: str) -> None:
    required = PREDICTION_COLUMNS | ({"Type"} if interval == "hilo" else set())
    count = 0
    for row in _rows(path, asset, required):
        float(row["Prediction"])
        if interval == "hilo" and row["Type"] not in {"H", "L"}:
            raise ValueError("unrecognized high/low prediction type")
        count += 1
    if not count:
        raise ValueError("no tide predictions returned")


class CoopsParams(BaseModel):
    """Which CO-OPS station, vertical datum, and unit system one query names."""

    model_config = ConfigDict(extra="forbid")

    station: str = Field(
        description="Required seven-digit CO-OPS station id, for example '8518750'."
    )
    datum: str = Field(description=f"Required vertical datum: {', '.join(sorted(DATUMS))}.")
    units: Annotated[str, choice("metric", "english")] = Field(
        default="metric", description="metric (default) or english."
    )

    @field_validator("station", mode="before")
    @classmethod
    def _one_station_id(cls, value: object) -> object:
        """One station per request, spelled as the seven ASCII digits the API addresses."""
        if (
            not isinstance(value, str)
            or len(value) != 7
            or not value.isascii()
            or not value.isdigit()
        ):
            raise ValueError("must be a seven-digit string, for example '8518750'")
        return value

    @field_validator("datum", mode="before")
    @classmethod
    def _explicit_datum(cls, value: object) -> object:
        """Never defaulted: a water level means nothing without the datum it is measured from."""
        if not isinstance(value, str) or value not in DATUMS:
            raise ValueError(f"must be explicit: {', '.join(sorted(DATUMS))}")
        return value


class CoopsPredictionParams(CoopsParams):
    """A tide-prediction query also names the interval its series steps on."""

    interval: str = Field(
        default="6",
        description="6 (default), 1, 5, 10, 15, 30, or 60 minutes; h (hourly); hilo (high/low).",
    )

    @field_validator("interval", mode="before")
    @classmethod
    def _api_token(cls, value: object) -> object:
        """Normalize to the exact token the API accepts, folding case and integer minutes."""
        message = "must be h, hilo, or minutes: 1, 5, 6, 10, 15, 30, or 60"
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValueError(message)
        token = str(value).strip().lower()
        if token not in INTERVALS:
            raise ValueError(message)
        return token


class _CoopsStation(HttpProvider):
    """Shared window, request, and validation rules for CO-OPS station products."""

    product: ClassVar[str]
    label: ClassVar[str]

    def _window(self, query: Query, limit: timedelta) -> tuple[datetime, datetime]:
        start, end = self.utc_window(query)
        if end.time() == LAST_INSTANT:
            end = end.replace(second=0, microsecond=0)  # a bare end date: its last minute
        if any(value.second or value.microsecond for value in (start, end)):
            raise QueryError("CO-OPS timestamps must have minute precision (zero seconds)")
        if end - start > limit:
            raise QueryError(
                f"CO-OPS {self.label} requests must span at most {limit.days} days; "
                "split longer intervals"
            )
        return start, end

    def _asset(
        self,
        station: str,
        start: datetime,
        end: datetime,
        params: dict[str, str],
    ) -> Asset:
        url = str(
            httpx.URL(
                DATA_URL,
                params={
                    "station": station,
                    "product": self.product,
                    "begin_date": start.strftime("%Y%m%d %H:%M"),
                    "end_date": end.strftime("%Y%m%d %H:%M"),
                    **params,
                    "time_zone": "gmt",
                    "format": "csv",
                    "application": "usdata",
                },
            )
        )
        digest = hashlib.sha256(url.encode()).hexdigest()[:16]
        return Asset(
            id=f"{self.product}_{station}_{digest}.csv",
            dataset_id=self.dataset.id,
            href=url,
            protocol=Protocol.HTTP,
            media_type="text/csv",
            time=TimeRange(start=start, end=end),
        )

    def _validate(self, path: Path, asset: Asset) -> None:
        raise NotImplementedError

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download raw CSV, validating the response before replacing the destination."""
        with staged_path(dest) as temporary:
            http.download(asset.href, temporary, self._http())
            try:
                self._validate(temporary, asset)
            except (ValueError, UnicodeError, csv.Error) as error:
                raise httpx.DecodingError(
                    f"CO-OPS returned no usable {self.label} CSV: {error}",
                    request=httpx.Request("GET", asset.href),
                ) from error
        return dest


class CoopsWaterLevels(_CoopsStation):
    """One station's observed water levels, preserving source units and quality fields."""

    product = "water_level"
    label = "water-level"
    params_model = CoopsParams

    def list_assets(self, query: Query) -> list[Asset]:
        """Describe one bounded CSV request; availability is checked during fetching."""
        params = self.parse_params(query, CoopsParams)
        self.reject(query, "bbox", "text", "variables", hint="CO-OPS requires an explicit station")
        start, end = self._window(query, MAX_INTERVAL)
        request = {"datum": params.datum, "units": params.units}
        return [self._asset(params.station, start, end, request)]

    def _validate(self, path: Path, asset: Asset) -> None:
        _validate_observations(path, asset)


class CoopsTidePredictions(_CoopsStation):
    """One station's astronomical tide predictions on a chosen interval."""

    product = "predictions"
    label = "tide-prediction"
    params_model = CoopsPredictionParams

    def list_assets(self, query: Query) -> list[Asset]:
        """Describe one bounded CSV request; subordinate stations only serve hilo."""
        params = self.parse_params(query, CoopsPredictionParams)
        self.reject(query, "bbox", "text", "variables", hint="CO-OPS requires an explicit station")
        start, end = self._window(query, MAX_PREDICTION_INTERVAL)
        request = {"datum": params.datum, "units": params.units, "interval": params.interval}
        return [self._asset(params.station, start, end, request)]

    def _validate(self, path: Path, asset: Asset) -> None:
        interval = httpx.URL(asset.href).params.get("interval", "6")
        _validate_predictions(path, asset, interval)
