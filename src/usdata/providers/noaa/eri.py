"""NGS Emergency Response Imagery: post-event aerial GeoTIFFs in the public noaa-eri-pds bucket.

Require ``event``, one top-level folder named exactly as the bucket names it,
such as ``2020_Nashville_Tornado``. ``collection`` narrows the event to one or
more folders under it, usually flights such as ``20200307a_RGB``. Every ``.tif``
in a collection is one asset, fetched whole; the ``raw/`` camera frames and the
``downloads/`` archives are not part of the dataset.

A bbox keeps the files whose footprint meets it. A tile's name states its
north-west corner, in degrees, minutes, and seconds or, in a folder that names
its UTM zone, in UTM metres; the size of the collection's tiles is read from one
tile's GeoTIFF header. A flight mosaic named after its folder is placed by its
own header. A collection whose files cannot be placed that way refuses a bbox
rather than returning unfiltered files (ADR 0052).

Flight folders carry local calendar dates rather than UTC instants, and some
carry none, so start and end are refused; an asset's ``time`` is the local day
its folder names, as UTC, or an interval open from the event's year.
"""

from __future__ import annotations

import difflib
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from usdata.models import Asset, BBox, Protocol, Query, TimeRange
from usdata.protocols import s3
from usdata.providers.base import QueryError
from usdata.providers.http import HttpProvider
from usdata.providers.noaa import utm
from usdata.providers.noaa.geotiff import (
    MODEL_GEOGRAPHIC,
    MODEL_PROJECTED,
    Georeference,
    GeoTiffError,
    read_georeference,
)
from usdata.providers.params import StrList, positive_int

BUCKET = "noaa-eri-pds"
MEDIA_TYPE = "image/tiff; application=geotiff"
DEFAULT_MAX_GB = 25
GIGABYTE = 10**9
EVENT_RE = re.compile(r"\d{4}_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*")
_SEGMENT = r"[A-Za-z0-9][A-Za-z0-9._-]*"
COLLECTION_RE = re.compile(rf"{_SEGMENT}(?:/{_SEGMENT})*")
RAW, DOWNLOADS = "raw", "downloads"
DMS_TILE = re.compile(
    r"(?<!\d)(?P<lon>\d{3})(?P<lon_min>\d{2})(?P<lon_sec>\d{2})(?P<ew>[we])"
    r"(?P<lat>\d{2})(?P<lat_min>\d{2})(?P<lat_sec>\d{2})(?P<ns>[ns])\.tif$"
)
UTM_TILE = re.compile(r"(?<!\d)(?P<easting>\d{6})e(?P<northing>\d{7})n\.tif$")
UTM_ZONE_FOLDER = re.compile(r"UTMZone(?P<zone>\d{1,2})$")
DEGREE_TOLERANCE = 2 / 3600
"""How far a footprint is widened, in degrees: a name's truncated second plus the tile's buffer."""
METRE_TOLERANCE = 100.0
"""How far a UTM tile's footprint is widened, in metres: its buffer, at most 50 m where probed."""
WEB_MERCATOR = 3857
WEB_MERCATOR_RADIUS = 6378137.0
DATED_FOLDER = re.compile(r"(?P<date>\d{8})(?:_(?P<last>\d{2})_)?(?!\d)")
MONTH_DAY_FOLDER = re.compile(
    r"(?P<month>jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(?P<day>\d{2})(?!\d)"
)
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
EARLIEST_OFFSET, LATEST_OFFSET = timedelta(hours=4), timedelta(hours=10)
"""A local calendar day in U.S. time zones: UTC-4 (Atlantic, Eastern daylight) to UTC-10."""


class EmergencyResponseImageryParams(BaseModel):
    """Which event, which of its folders, and how many bytes one query may select."""

    model_config = ConfigDict(extra="forbid")

    event: str = Field(
        description=(
            "Required event folder, exactly as the bucket names it, such as 2020_Nashville_Tornado."
        )
    )
    collection: StrList | None = Field(
        default=None,
        description=(
            "Folder(s) under the event, such as the flight 20200307a_RGB: one, a list, or "
            "comma-separated; default every folder."
        ),
    )
    max_gb: Annotated[int, positive_int()] = Field(
        default=DEFAULT_MAX_GB,
        description=(
            f"Refuse a selection larger than this many gigabytes (10^9 bytes); "
            f"default {DEFAULT_MAX_GB}."
        ),
    )

    @field_validator("event")
    @classmethod
    def _an_event_folder(cls, value: str) -> str:
        if not EVENT_RE.fullmatch(value):
            raise ValueError(
                "must be an event folder such as 2020_Nashville_Tornado: a year, an underscore, "
                "and letters, digits, or underscores, with no slash"
            )
        return value

    @field_validator("collection")
    @classmethod
    def _folders_under_the_event(cls, value: list[str] | None) -> list[str] | None:
        for item in value or []:
            if not COLLECTION_RE.fullmatch(item):
                raise ValueError(
                    f"must name folders under the event, such as 20200307a_RGB, not {item!r}"
                )
            if _excluded(item):
                raise ValueError(
                    f"cannot name {item!r}: raw/ and downloads/ folders hold camera frames and "
                    "archives, not this dataset's GeoTIFFs"
                )
        return value


def _excluded(folder: str) -> bool:
    """Whether a folder, relative to its event, holds raw frames or download archives."""
    parts = folder.split("/")
    return parts[0] == DOWNLOADS or RAW in parts


def _collection_of(event: str, key: str) -> str | None:
    """The folder under ``event`` holding the GeoTIFF ``key``, or None for any other object."""
    root = f"{event}/"
    if not key.startswith(root):
        return None
    folder, _, name = key.removeprefix(root).rpartition("/")
    if not folder or not name.lower().endswith(".tif") or _excluded(folder):
        return None
    return folder


def flight_time(event: str, collection: str) -> TimeRange:
    """When a folder's imagery was flown, as far as the folder and event names say.

    A folder named for its flight's date, ``20200307a_RGB`` or, with the event's
    year, ``may24JPEGtiles_UTMZone15``, states a local calendar date; frames in
    the raw folders carry UTC times past midnight for evening flights. That day
    is returned as the UTC interval it covers in any U.S. time zone. A folder
    naming no date, such as ``WILMA_29907494_1`` or ``EC2301a_OB_N_RGB``, gives
    only the event's year, returned as an interval open at its end.
    """
    folder = collection.split("/", 1)[0]
    year = int(event[:4])
    first = last = None
    try:
        if match := DATED_FOLDER.match(folder):
            first = datetime.strptime(match["date"], "%Y%m%d").replace(tzinfo=UTC)
            last = first.replace(day=int(match["last"])) if match["last"] else first
        elif match := MONTH_DAY_FOLDER.match(folder):
            month = MONTHS.index(match["month"]) + 1
            first = last = datetime(year, month, int(match["day"]), tzinfo=UTC)
    except ValueError:
        first = last = None
    if first is None or last is None or last < first:
        return TimeRange(start=datetime(year, 1, 1, tzinfo=UTC))
    return TimeRange(start=first + EARLIEST_OFFSET, end=last + timedelta(days=1) + LATEST_OFFSET)


def utm_zone(collection: str) -> int | None:
    """The UTM zone a collection's folder name states, as in ``may24JPEGtiles_UTMZone15``."""
    match = UTM_ZONE_FOLDER.search(collection.rsplit("/", 1)[-1])
    zone = int(match["zone"]) if match else None
    return zone if zone is not None and 1 <= zone <= 60 else None


@dataclass(frozen=True)
class Corner:
    """The north-west corner a tile's name states: degrees, or UTM metres in ``zone``."""

    x: float
    y: float
    zone: int | None = None


def corner(collection: str, name: str) -> Corner | None:
    """The corner ``name`` states, or None when it states none this adapter can read.

    ``0852700w360900n`` is 85°27'00"W, 36°09'00"N. Some names truncate a second,
    writing ``3044`` for 30'45", which the footprint tolerance covers.
    ``350000e4102500n`` is UTM easting and northing, read only in a folder that
    names its zone, since the GeoTIFFs themselves state none.
    """
    if match := DMS_TILE.search(name):
        minutes = (match["lon_min"], match["lon_sec"], match["lat_min"], match["lat_sec"])
        if any(int(part) >= 60 for part in minutes):
            return None
        lon = int(match["lon"]) + int(match["lon_min"]) / 60 + int(match["lon_sec"]) / 3600
        lat = int(match["lat"]) + int(match["lat_min"]) / 60 + int(match["lat_sec"]) / 3600
        if lon > 180 or lat > 90:
            return None
        return Corner(-lon if match["ew"] == "w" else lon, -lat if match["ns"] == "s" else lat)
    if (match := UTM_TILE.search(name)) and (zone := utm_zone(collection)) is not None:
        return Corner(float(match["easting"]), float(match["northing"]), zone)
    return None


def footprint(tile: Corner, span: tuple[float, float]) -> BBox:
    """A box holding the whole tile whose corner is ``tile`` and whose size is ``span``.

    The box is widened on every side by the tolerance, so it holds the tile even
    where the name truncates a second and where the tile carries a buffer past
    its nominal edge.
    """
    width, height = span
    if tile.zone is None:
        pad = DEGREE_TOLERANCE
        return BBox(
            west=max(tile.x - pad, -180),
            south=max(tile.y - height - pad, -90),
            east=min(tile.x + width + pad, 180),
            north=min(tile.y + pad, 90),
        )
    pad = METRE_TOLERANCE
    xs = (tile.x - pad, tile.x + width / 2, tile.x + width + pad)
    ys = (tile.y - height - pad, tile.y - height / 2, tile.y + pad)
    points = [utm.to_lonlat(tile.zone, x, y) for x in xs for y in ys]
    return BBox(
        west=min(lon for lon, _ in points),
        south=min(lat for _, lat in points),
        east=max(lon for lon, _ in points),
        north=max(lat for _, lat in points),
    )


def _agrees(tile: Corner, georeference: Georeference) -> bool:
    """Whether a tile's header places it where its name says, so the name can place its siblings."""
    if tile.zone is None:
        tolerance, wrong_model = DEGREE_TOLERANCE, MODEL_PROJECTED
    else:
        tolerance, wrong_model = METRE_TOLERANCE, MODEL_GEOGRAPHIC
    return (
        georeference.model_type != wrong_model
        and abs(georeference.west - tile.x) <= tolerance
        and abs(georeference.north - tile.y) <= tolerance
    )


def _web_mercator(x: float, y: float) -> tuple[float, float]:
    """Longitude and latitude in degrees of a spherical Web Mercator coordinate (EPSG:3857)."""
    return math.degrees(x / WEB_MERCATOR_RADIUS), math.degrees(
        math.atan(math.sinh(y / WEB_MERCATOR_RADIUS))
    )


def _mosaic_footprint(georeference: Georeference) -> BBox | None:
    """The box a mosaic's header states, or None unless it is in degrees or Web Mercator."""
    west, south, east, north = georeference.extent
    if georeference.model_type == MODEL_PROJECTED and georeference.projected_crs == WEB_MERCATOR:
        (west, south), (east, north) = _web_mercator(west, south), _web_mercator(east, north)
    elif georeference.model_type != MODEL_GEOGRAPHIC:
        return None
    return BBox(
        west=max(west, -180), south=max(south, -90), east=min(east, 180), north=min(north, 90)
    )


def _named(items: Iterable[str], limit: int = 8) -> str:
    """Up to ``limit`` names joined by commas, saying how many more there are."""
    ordered = list(items)
    shown = ", ".join(ordered[:limit])
    return f"{shown}, and {len(ordered) - limit} more" if len(ordered) > limit else shown


def _near(name: str, choices: list[str]) -> str:
    """'did you mean ...; ' for close spellings of ``name``, or nothing."""
    close = difflib.get_close_matches(name, choices, n=5, cutoff=0.6)
    return f"did you mean {', '.join(close)}? " if close else ""


def _gigabytes(size: int) -> str:
    return f"{size / GIGABYTE:.1f} GB"


class EmergencyResponseImagery(HttpProvider):
    """Whole post-event GeoTIFFs by event, folder, and optionally the footprint a bbox meets."""

    params_model = EmergencyResponseImageryParams

    def list_assets(self, query: Query) -> list[Asset]:
        """List the event's GeoTIFFs in the chosen folders, kept by footprint given a bbox."""
        params = self.parse_params(query, EmergencyResponseImageryParams)
        self.reject(
            query,
            "text",
            "variables",
            hint="each GeoTIFF is fetched whole, every band; select with event and collection",
        )
        self.reject(
            query,
            "time",
            hint="flight folders carry local dates, not UTC times; choose flights with collection",
        )
        event = params.event
        found = self._collections(event, params.collection)
        if params.collection is not None:
            if missing := [name for name in params.collection if name not in found]:
                known = sorted(self._collections(event, None))
                raise QueryError(
                    f"{event} has no collection {', '.join(missing)}; "
                    f"{_near(missing[0], known)}its collections are {_named(known, 50)}"
                )
            found = {name: found[name] for name in params.collection}
        if not found:
            raise QueryError(f"{event} holds no GeoTIFF outside its raw/ and downloads/ folders")
        placed = self._placed(event, found, query.bbox) if query.bbox is not None else None
        assets = [
            self._asset(obj, event, collection, None if placed is None else placed[obj.key])
            for collection, objects in found.items()
            for obj in objects
            if placed is None or obj.key in placed
        ]
        self._within_budget(event, assets, params.max_gb)
        return sorted(assets, key=lambda asset: asset.id)

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download the whole GeoTIFF without modification."""
        return s3.download(asset.href, dest, self._http())

    def _asset(self, obj: s3.S3Object, event: str, collection: str, box: BBox | None) -> Asset:
        zone = utm_zone(collection)
        return Asset(
            id=obj.key,
            dataset_id=self.dataset.id,
            href=f"s3://{BUCKET}/{obj.key}",
            protocol=Protocol.S3,
            media_type=MEDIA_TYPE,
            size=obj.size,
            time=flight_time(event, collection),
            bbox=box,
            properties={} if zone is None else {"utm_zone": str(zone)},
        )

    def _collections(self, event: str, wanted: list[str] | None) -> dict[str, list[s3.S3Object]]:
        """Every GeoTIFF of ``event`` by folder, walking only toward the ``wanted`` folders.

        One ``/``-delimited listing per folder skips the thousands of raw frames
        beside the tiles. Each object is placed by its own key, not by which
        listing returned it.

        Raises:
            QueryError: The bucket has no such event.
        """
        client = self._http()
        root = f"{event}/"
        found: dict[str, dict[str, s3.S3Object]] = {}
        pending, listed = [root], False
        while pending:
            objects, prefixes = s3.list_directory(BUCKET, pending.pop(), client)
            listed = listed or bool(objects or prefixes)
            for obj in objects:
                if (collection := _collection_of(event, obj.key)) is not None:
                    found.setdefault(collection, {})[obj.key] = obj
            for prefix in prefixes:
                folder = prefix.removeprefix(root).rstrip("/")
                if not prefix.startswith(root) or not folder or _excluded(folder):
                    continue
                if wanted is None or any(w == folder or w.startswith(f"{folder}/") for w in wanted):
                    pending.append(prefix)
        if not listed:
            _, prefixes = s3.list_directory(BUCKET, "", client)
            events = sorted(prefix.rstrip("/") for prefix in prefixes)
            raise QueryError(
                f"{BUCKET} has no event {event}; {_near(event, events)}"
                f"its events are {_named(events, 100)}"
            )
        return {
            collection: sorted(objects.values(), key=lambda obj: obj.key)
            for collection, objects in sorted(found.items())
        }

    def _placed(
        self, event: str, found: dict[str, list[s3.S3Object]], bbox: BBox
    ) -> dict[str, BBox]:
        """The footprint of every file that meets ``bbox``, by key.

        Raises:
            QueryError: A folder holds files whose names give no footprint, or a
                tile's header disagrees with its name.
        """
        tiles: dict[str, list[tuple[s3.S3Object, Corner]]] = {}
        mosaics: dict[str, s3.S3Object] = {}
        unplaced: dict[str, str] = {}
        for collection, objects in found.items():
            mosaic_name = f"{collection.rsplit('/', 1)[-1]}.tif"
            for obj in objects:
                name = obj.key.rsplit("/", 1)[-1]
                if (tile := corner(collection, name)) is not None:
                    tiles.setdefault(collection, []).append((obj, tile))
                elif name == mosaic_name:
                    mosaics[collection] = obj
                else:
                    unplaced.setdefault(collection, name)
        if unplaced:
            placeable = [name for name in found if name not in unplaced]
            examples = [f"{name} (such as {file})" for name, file in unplaced.items()]
            hint = (
                f"name folders it can place with collection=, such as {_named(placeable)}"
                if placeable
                else "list the event without a bbox"
            )
            raise QueryError(
                f"{self.dataset.id} cannot filter {event} by location/bbox: the file names in "
                f"{_named(examples, 4)} state no footprint; {hint}"
            )
        kept: dict[str, BBox] = {}
        for collection, members in tiles.items():
            sample, sample_corner = members[0]
            georeference = self._georeference(sample.key)
            if not _agrees(sample_corner, georeference):
                raise QueryError(
                    f"{self.dataset.id} cannot filter {event}/{collection} by location/bbox: "
                    f"{sample.key} is not georeferenced where its name places it"
                )
            span = georeference.span
            for obj, tile in members:
                box = footprint(tile, span)
                if box.intersects(bbox):
                    kept[obj.key] = box
        for collection, obj in mosaics.items():
            box = _mosaic_footprint(self._georeference(obj.key))
            if box is None:
                raise QueryError(
                    f"{self.dataset.id} cannot filter {event}/{collection} by location/bbox: "
                    f"the mosaic {obj.key} is georeferenced neither in degrees nor in Web Mercator"
                )
            if box.intersects(bbox):
                kept[obj.key] = box
        return kept

    def _georeference(self, key: str) -> Georeference:
        try:
            return read_georeference(s3.https_url(BUCKET, key), self._http())
        except GeoTiffError as error:
            raise QueryError(f"cannot read the georeferencing of {key}: {error}") from None

    def _within_budget(self, event: str, assets: list[Asset], max_gb: int) -> None:
        """Refuse a selection over ``max_gb``, saying where its bytes are.

        Raises:
            QueryError: The listed sizes add up to more than ``max_gb`` gigabytes.
        """
        total = sum(asset.size or 0 for asset in assets)
        if total <= max_gb * GIGABYTE:
            return
        by_folder: dict[str, list[int]] = {}
        for asset in assets:
            folder = asset.id.removeprefix(f"{event}/").rpartition("/")[0]
            by_folder.setdefault(folder, []).append(asset.size or 0)
        largest = sorted(by_folder.items(), key=lambda item: -sum(item[1]))
        shares = [f"{name} {len(sizes)} files {_gigabytes(sum(sizes))}" for name, sizes in largest]
        raise QueryError(
            f"{event} selects {len(assets)} files, {_gigabytes(total)}, more than max_gb={max_gb}; "
            f"narrow it with a bbox or collection, or raise max_gb. Largest collections: "
            f"{_named(shares, 5)}"
        )
