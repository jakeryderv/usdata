"""Build a normalized ``Query`` from the loose arguments users actually type."""

from __future__ import annotations

from datetime import UTC, date, datetime
from functools import lru_cache
from importlib import resources
from typing import Any

import yaml

from usdata.models import BBox, Query, TimeRange


class UnknownPlace(ValueError):
    """A place name that is not in the bundled place table."""

    pass


@lru_cache(maxsize=1)
def _places() -> dict[str, BBox]:
    raw = yaml.safe_load((resources.files("usdata.data") / "places.yaml").read_text()) or {}
    table: dict[str, BBox] = {}
    for name, spec in raw.get("places", {}).items():
        box = BBox.model_validate(spec["bbox"])
        table[name.lower()] = box
        for alias in spec.get("aliases", []):
            table[str(alias).lower()] = box
    return table


def resolve_place(name: str) -> BBox:
    """Map a state name or postal code to a bounding box."""
    try:
        return _places()[name.strip().lower()]
    except KeyError:
        raise UnknownPlace(name) from None


def parse_datetime(value: str | date | datetime | None) -> datetime | None:
    """Accept ISO dates or datetimes; naive values are treated as UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime(value.year, value.month, value.day)
    else:
        dt = datetime.fromisoformat(value.strip())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def build_query(
    text: str | None = None,
    *,
    provider: str | None = None,
    location: str | None = None,
    bbox: BBox | tuple[float, float, float, float] | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float = 50.0,
    start: str | date | datetime | None = None,
    end: str | date | datetime | None = None,
    variables: list[str] | None = None,
    **params: Any,
) -> Query:
    """Normalize user-facing arguments into a ``Query``.

    Exactly one of ``location``, ``bbox``, or ``lat``/``lon`` may set the spatial filter.
    """
    spatial = [x is not None for x in (location, bbox, lat)]
    if sum(spatial) > 1:
        raise ValueError("pass only one of location, bbox, or lat/lon")
    if (lat is None) != (lon is None):
        raise ValueError("lat and lon must be given together")

    box: BBox | None = None
    if location is not None:
        box = resolve_place(location)
    elif bbox is not None:
        box = (
            bbox
            if isinstance(bbox, BBox)
            else BBox(west=bbox[0], south=bbox[1], east=bbox[2], north=bbox[3])
        )
    elif lat is not None and lon is not None:
        box = BBox.from_point(lat, lon, radius_km)

    start_dt, end_dt = parse_datetime(start), parse_datetime(end)
    time = TimeRange(start=start_dt, end=end_dt) if (start_dt or end_dt) else None

    return Query(
        text=text,
        provider=provider,
        bbox=box,
        time=time,
        variables=list(variables or []),
        params=params,
    )
