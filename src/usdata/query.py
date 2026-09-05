"""Build a normalized ``Query`` from the loose arguments users actually type."""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime
from functools import lru_cache
from importlib import resources
from typing import Any

from usdata.models import BBox, Query, TimeRange


class UnknownPlace(ValueError):
    """A place name that is not in the bundled place table."""

    pass


class AmbiguousPlace(UnknownPlace):
    """A county name matches multiple places; qualify it with a state or FIPS."""


@lru_cache(maxsize=1)
def _places() -> tuple[dict[str, set[str]], dict[str, tuple[str, BBox]]]:
    data = (resources.files("usdata.data") / "places.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(data)))
    aliases: dict[str, set[str]] = {}
    places: dict[str, tuple[str, BBox]] = {}

    def add(alias: str, geoid: str) -> None:
        aliases.setdefault(alias.casefold(), set()).add(geoid)

    for row in rows:
        geoid = row["geoid"]
        box = BBox(**{key: float(row[key]) for key in ("west", "south", "east", "north")})
        label = (
            row["name"] if row["kind"] == "state" else f"{row['qualified_name']}, {row['state']}"
        )
        places[geoid] = (label, box)
        add(geoid, geoid)
        if row["kind"] == "state":
            add(row["name"], geoid)
            add(row["state"], geoid)
    state_aliases = set(aliases)
    for row in rows:
        if row["kind"] != "county":
            continue
        geoid = row["geoid"]
        for county in (row["name"], row["qualified_name"]):
            for state in (row["state"], row["state_name"]):
                add(f"{county}, {state}", geoid)
        # Bare qualified names are useful, but must not shadow state names.
        if row["qualified_name"].casefold() not in state_aliases:
            add(row["qualified_name"], geoid)
    return aliases, places


def resolve_place(name: str) -> BBox:
    """Resolve a state, qualified county name, or quoted two/five-digit FIPS code."""
    key = ", ".join(" ".join(part.split()) for part in name.split(",")).casefold()
    aliases, places = _places()
    candidates = aliases.get(key, set())
    if not candidates:
        raise UnknownPlace(f"unknown place: {name!r}; use a state, 'County, ST', or quoted FIPS")
    if len(candidates) > 1:
        labels = sorted(places[geoid][0] for geoid in candidates)
        examples = "; ".join(labels[:5])
        suffix = "; ..." if len(labels) > 5 else ""
        raise AmbiguousPlace(f"ambiguous place {name!r}: {examples}{suffix}; use state or FIPS")
    return places[next(iter(candidates))][1]


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
