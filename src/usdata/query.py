"""Build a normalized ``Query`` from the loose arguments users actually type."""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime, time
from functools import lru_cache
from importlib import resources
from typing import Any

from usdata.models import BBox, Place, Query, TimeRange


class UnknownPlace(ValueError):
    """A place name that is not in the bundled place table."""

    pass


class AmbiguousPlace(UnknownPlace):
    """A county name matches multiple places; qualify it with a state or FIPS."""


@lru_cache(maxsize=1)
def _places() -> tuple[dict[str, set[str]], dict[str, tuple[Place, BBox]]]:
    data = (resources.files("usdata.data") / "places.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(data)))
    aliases: dict[str, set[str]] = {}
    places: dict[str, tuple[Place, BBox]] = {}

    def add(alias: str, geoid: str) -> None:
        aliases.setdefault(alias.casefold(), set()).add(geoid)

    for row in rows:
        geoid = row["geoid"]
        box = BBox(**{key: float(row[key]) for key in ("west", "south", "east", "north")})
        label = (
            row["name"] if row["kind"] == "state" else f"{row['qualified_name']}, {row['state']}"
        )
        kind = "state" if row["kind"] == "state" else "county"
        places[geoid] = (Place(kind=kind, geoid=geoid, label=label, state=row["state"]), box)
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
    """Resolve a state, qualified county name, or quoted two/five-digit FIPS code to its box."""
    return find_place(name)[1]


def find_place(name: str) -> tuple[Place, BBox]:
    """Resolve a location to the place the table identifies and the rectangle enclosing it.

    Args:
        name: A state name or postal code, ``'County, ST'``, or a quoted two- or
            five-digit FIPS code.

    Returns:
        The place, which keeps the FIPS code a rectangle cannot give back, and its box.

    Raises:
        UnknownPlace: The table holds no such place.
        AmbiguousPlace: A bare county name matches more than one state's county.
    """
    key = ", ".join(" ".join(part.split()) for part in name.split(",")).casefold()
    aliases, places = _places()
    candidates = aliases.get(key, set())
    if not candidates:
        raise UnknownPlace(f"unknown place: {name!r}; use a state, 'County, ST', or quoted FIPS")
    if len(candidates) > 1:
        labels = sorted(places[geoid][0].label for geoid in candidates)
        examples = "; ".join(labels[:5])
        suffix = "; ..." if len(labels) > 5 else ""
        raise AmbiguousPlace(f"ambiguous place {name!r}: {examples}{suffix}; use state or FIPS")
    return places[next(iter(candidates))]


LAST_INSTANT = time(23, 59, 59, 999999)
"""The time of day a bare end date resolves to: the last microsecond of its UTC day."""


def parse_datetime(value: str | date | datetime | None, *, end: bool = False) -> datetime | None:
    """Accept ISO dates or datetimes; naive values are treated as UTC.

    A date alone is the first instant of its UTC day, or with ``end=True`` the
    last, ``23:59:59.999999``, so a window bounded by two bare dates covers
    whole calendar days. Every ISO 8601 date spelling Python reads counts as a
    date alone, compact ``20240507`` and week-form ``2024-W19-2`` included. A
    datetime is taken as given, whichever bound it is.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, LAST_INSTANT if end else time.min)
    else:
        text = value.strip()
        try:
            day = date.fromisoformat(text)
        except ValueError:
            dt = datetime.fromisoformat(text)
        else:
            dt = datetime.combine(day, LAST_INSTANT if end else time.min)
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
    A ``location`` sets both the query's ``bbox`` and its ``place``, the state or
    county it named; a ``bbox`` or a ``lat``/``lon`` names no place.
    """
    spatial = [x is not None for x in (location, bbox, lat)]
    if sum(spatial) > 1:
        raise ValueError("pass only one of location, bbox, or lat/lon")
    if (lat is None) != (lon is None):
        raise ValueError("lat and lon must be given together")

    box: BBox | None = None
    place: Place | None = None
    if location is not None:
        place, box = find_place(location)
    elif bbox is not None:
        box = (
            bbox
            if isinstance(bbox, BBox)
            else BBox(west=bbox[0], south=bbox[1], east=bbox[2], north=bbox[3])
        )
    elif lat is not None and lon is not None:
        box = BBox.from_point(lat, lon, radius_km)

    start_dt, end_dt = parse_datetime(start), parse_datetime(end, end=True)
    time = TimeRange(start=start_dt, end=end_dt) if (start_dt or end_dt) else None

    return Query(
        text=text,
        provider=provider,
        bbox=box,
        place=place,
        time=time,
        variables=list(variables or []),
        params=params,
    )
