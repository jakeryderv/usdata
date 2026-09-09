"""Observed six-minute CO-OPS water levels as raw CSV.

Params: one seven-digit ``station``, an explicit ``datum``, and optional
``units`` (metric or english). Both dates are required at minute precision;
requests use UTC and span at most 28 days. Predictions are not included.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from usdata._files import staged_path
from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.providers._http import _HttpProvider
from usdata.providers.base import QueryError

DATA_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
DATUMS = {"CRD", "IGLD", "LWD", "MHHW", "MHW", "MTL", "MSL", "MLW", "MLLW", "NAVD", "STND"}
MAX_INTERVAL = timedelta(days=28)
REQUIRED_COLUMNS = {
    "Date Time",
    "Water Level",
    "Sigma",
    "O or I (for verified)",
    "F",
    "R",
    "L",
    "Quality",
}


def _validate_csv(path: Path, asset: Asset) -> None:
    """Reject error documents and malformed/empty responses before committing bytes."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            records = csv.reader(stream, strict=True)
            columns = [name.strip() for name in next(records, [])]
            if (
                any(not name for name in columns)
                or len(set(columns)) != len(columns)
                or not REQUIRED_COLUMNS.issubset(columns)
            ):
                raise ValueError("missing expected water-level CSV columns")
            count = 0
            for values in records:
                if values and values[0].startswith("Error:"):
                    raise ValueError(values[0][:512])
                if len(values) != len(columns):
                    raise ValueError("CSV row does not match the header")
                row = dict(zip(columns, values, strict=True))
                when = datetime.strptime(row["Date Time"].strip(), "%Y-%m-%d %H:%M").replace(
                    tzinfo=UTC
                )
                if asset.time is not None and not asset.time.overlaps(
                    TimeRange(start=when, end=when)
                ):
                    raise ValueError("observation lies outside the requested interval")
                if row["Quality"].strip() not in {"p", "v"}:
                    raise ValueError("unrecognized observation quality")
                for field in ("Water Level", "Sigma"):
                    if row[field].strip():
                        float(row[field])
                count += 1
            if not count:
                raise ValueError("no water-level observations returned")
    except (ValueError, UnicodeError, csv.Error) as error:
        raise httpx.DecodingError(
            f"CO-OPS returned no usable water-level CSV: {error}",
            request=httpx.Request("GET", asset.href),
        ) from error


class CoopsWaterLevels(_HttpProvider):
    """One station's observed water levels, preserving source units and quality fields."""

    def list_assets(self, query: Query) -> list[Asset]:
        """Describe one bounded CSV request; availability is checked during fetching."""
        if unknown := set(query.params) - {"station", "datum", "units"}:
            raise QueryError(f"unsupported {self.dataset.id} params: {', '.join(sorted(unknown))}")
        if query.bbox is not None or query.text is not None or query.variables:
            raise QueryError(
                "CO-OPS requires an explicit station; location, text and variables are unsupported"
            )
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
        if query.time is None or query.time.start is None or query.time.end is None:
            raise QueryError(f"{self.dataset.id} requires both start and end timestamps")
        start = query.time.start.replace(tzinfo=query.time.start.tzinfo or UTC).astimezone(UTC)
        end = query.time.end.replace(tzinfo=query.time.end.tzinfo or UTC).astimezone(UTC)
        if any(value.second or value.microsecond for value in (start, end)):
            raise QueryError("CO-OPS timestamps must have minute precision (zero seconds)")
        if end - start > MAX_INTERVAL:
            raise QueryError("CO-OPS requests must span at most 28 days; split longer intervals")
        params = {
            "station": station,
            "product": "water_level",
            "begin_date": start.strftime("%Y%m%d %H:%M"),
            "end_date": end.strftime("%Y%m%d %H:%M"),
            "datum": datum,
            "units": units,
            "time_zone": "gmt",
            "format": "csv",
            "application": "usdata",
        }
        url = str(httpx.URL(DATA_URL, params=params))
        digest = hashlib.sha256(url.encode()).hexdigest()[:16]
        return [
            Asset(
                id=f"water_level_{station}_{digest}.csv",
                dataset_id=self.dataset.id,
                href=url,
                protocol=Protocol.HTTP,
                media_type="text/csv",
                time=TimeRange(start=start, end=end),
            )
        ]

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download raw CSV, validating the response before replacing the destination."""
        with staged_path(dest) as temporary:
            http.download(asset.href, temporary, self._http())
            _validate_csv(temporary, asset)
        return dest
