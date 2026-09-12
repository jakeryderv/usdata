"""CO-OPS observed water levels and tide predictions as raw CSV.

Both datasets share one station model: one seven-digit ``station``, an explicit
``datum``, optional ``units`` (metric or english), and both timestamps at minute
precision, requested in UTC. Observations span at most 28 days; predictions
span at most a year on any ``interval`` (six-minute by default, another minute
step, hourly, or high/low), within NOAA's own limits.
"""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

import httpx

from usdata._files import staged_path
from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.providers._http import _HttpProvider
from usdata.providers.base import QueryError

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


class _CoopsStation(_HttpProvider):
    """Shared station, datum, units, and window rules for CO-OPS station products."""

    product: ClassVar[str]
    label: ClassVar[str]

    def _station(self, query: Query) -> tuple[str, str, str]:
        station = query.params.get("station")
        if (
            not isinstance(station, str)
            or len(station) != 7
            or not station.isascii()
            or not station.isdigit()
        ):
            raise QueryError("station must be a seven-digit string, for example '8518750'")
        datum = query.params.get("datum")
        if not isinstance(datum, str) or datum not in DATUMS:
            raise QueryError(f"datum must be explicit: {', '.join(sorted(DATUMS))}")
        units = query.params.get("units", "metric")
        if units not in ("metric", "english"):
            raise QueryError("units must be metric or english")
        return station, datum, units

    def _window(self, query: Query, limit: timedelta) -> tuple[datetime, datetime]:
        start, end = self.utc_window(query)
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
    accepted_params: ClassVar[Mapping[str, str]] = {
        "station": "Required seven-digit CO-OPS station id, for example '8518750'.",
        "datum": f"Required vertical datum: {', '.join(sorted(DATUMS))}.",
        "units": "metric (default) or english.",
    }

    def list_assets(self, query: Query) -> list[Asset]:
        """Describe one bounded CSV request; availability is checked during fetching."""
        self.check_params(query)
        self.reject(query, "bbox", "text", "variables", hint="CO-OPS requires an explicit station")
        station, datum, units = self._station(query)
        start, end = self._window(query, MAX_INTERVAL)
        return [self._asset(station, start, end, {"datum": datum, "units": units})]

    def _validate(self, path: Path, asset: Asset) -> None:
        _validate_observations(path, asset)


def _interval(raw: Any) -> str:
    """Normalize ``interval`` to the exact token the API accepts."""
    if isinstance(raw, bool) or not isinstance(raw, (str, int)):
        raise QueryError("interval must be h, hilo, or minutes: 1, 5, 6, 10, 15, 30, or 60")
    value = str(raw).strip().lower()
    if value not in INTERVALS:
        raise QueryError("interval must be h, hilo, or minutes: 1, 5, 6, 10, 15, 30, or 60")
    return value


class CoopsTidePredictions(_CoopsStation):
    """One station's astronomical tide predictions on a chosen interval."""

    product = "predictions"
    label = "tide-prediction"
    accepted_params: ClassVar[Mapping[str, str]] = {
        **CoopsWaterLevels.accepted_params,
        "interval": "6 (default), 1, 5, 10, 15, 30, or 60 minutes; h (hourly); hilo (high/low).",
    }

    def list_assets(self, query: Query) -> list[Asset]:
        """Describe one bounded CSV request; subordinate stations only serve hilo."""
        self.check_params(query)
        self.reject(query, "bbox", "text", "variables", hint="CO-OPS requires an explicit station")
        station, datum, units = self._station(query)
        interval = _interval(query.params.get("interval", "6"))
        start, end = self._window(query, MAX_PREDICTION_INTERVAL)
        params = {"datum": datum, "units": units, "interval": interval}
        return [self._asset(station, start, end, params)]

    def _validate(self, path: Path, asset: Asset) -> None:
        interval = httpx.URL(asset.href).params.get("interval", "6")
        _validate_predictions(path, asset, interval)
