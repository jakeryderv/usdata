"""NWS damage surveys and their photos, from the Damage Assessment Toolkit's feature service.

National Weather Service offices survey damage after tornadoes and severe wind
and record it in the Damage Assessment Toolkit (DAT): damage points, each rated
on the Enhanced Fujita scale and often photographed; tornado tracks as lines;
and damage areas as polygons. The public ArcGIS FeatureServer serves the three
as layers 0, 1, and 2, with server-side filtering by SQL ``where`` clause and
envelope, and the photos as attachments of the points.

Two datasets read it (ADR 0051):

- ``noaa:nws-damage-surveys`` serves one layer's features as GeoJSON pages.
- ``noaa:nws-damage-photos`` serves each image attached to a damage point as
  one asset.

The window selects by the storm time: ``stormdate`` on points and polygons,
``starttime`` on lines, where ``stormdate`` is the same instant but was left
empty on one track. Times are UTC. A feature with no storm time is outside every
window unless ``include_undated`` asks for it.

The service is edited live, so a page is an object-id range rather than an
offset: listing asks for every matching id, sorts them, and cuts them into runs
of at most the layer's record limit, each asked for by its first and last id.
An edit then changes only the page whose range holds it. ``as_of`` reads the
layers as they stood at an instant through the service's archive, which begins
on 25 November 2020, so a pinned page cannot drift at all.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, NamedTuple

import httpx
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from usdata.models import Asset, BBox, Protocol, Query, TimeRange, as_utc
from usdata.protocols import arcgis, http
from usdata.providers.base import QueryError
from usdata.providers.http import HttpProvider
from usdata.providers.params import OptionalUpperStrList, StrList, choice, flag

SERVICE_URL = (
    "https://services.dat.noaa.gov/arcgis/rest/services/nws_damageassessmenttoolkit/"
    "DamageViewer/FeatureServer"
)
OBJECT_ID = "objectid"
MAX_WINDOW = timedelta(days=7)
"""The longest photo window; listing one asks for every point's attachments in batches."""

EF_RATINGS = (
    "EF0",
    "EF1",
    "EF2",
    "EF3",
    "EF3+",
    "EF4",
    "EF5",
    "EFU",
    "UNKNOWN",
    "N/A",
    "TSTM/Wind",
    "Tropical",
)
"""The ``efscale`` values the toolkit writes, spelled as it writes them."""

PHOTO_TYPES = {"image/jpeg": ".jpg", "image/png": ".png"}
"""Attachment types a photo asset may have, with the suffix its id takes."""


class Layer(NamedTuple):
    """One of the service's three layers and the fields a query uses on it."""

    number: int
    time_field: str
    office_field: str | None

    @property
    def url(self) -> str:
        """The layer's REST endpoint."""
        return f"{SERVICE_URL}/{self.number}"


LAYERS = {
    "points": Layer(0, "stormdate", "office"),
    "lines": Layer(1, "starttime", "wfo"),
    "polygons": Layer(2, "stormdate", None),
}


def _office(value: str) -> str:
    if len(value) != 3 or not value.isascii() or not value.isalpha():
        raise ValueError(f"office {value!r} must be a three-letter NWS office code such as TSA")
    return value


def _rating(value: str) -> str:
    for rating in EF_RATINGS:
        if value.upper() == rating.upper():
            return rating
    raise ValueError(f"efscale {value!r} must be one of {', '.join(EF_RATINGS)}")


def _instant(value: object) -> object:
    """A timestamp as text or a datetime; the numbers pydantic would read as epochs are refused."""
    if value is not None and not isinstance(value, (str, datetime)):
        raise ValueError("must be a UTC timestamp such as 2026-09-29T00:00Z")
    return value


class DamageFilters(BaseModel):
    """What narrows a damage query beyond its window and box, for either dataset."""

    model_config = ConfigDict(extra="forbid")

    office: OptionalUpperStrList = Field(
        default=None,
        description=(
            "NWS office code(s) that surveyed the damage, such as TSA or OUN; points and "
            "lines only, and a track shared by offices matches each of them."
        ),
    )
    efscale: StrList | None = Field(
        default=None,
        description=(
            "Rating(s) as the toolkit writes them: EF0 to EF5, EF3+, EFU, UNKNOWN, N/A, "
            "TSTM/Wind, or Tropical; case does not matter."
        ),
    )
    include_undated: Annotated[bool, flag()] = Field(
        default=False,
        description=(
            "Also return features with no storm time, which match every window; false by default."
        ),
    )
    as_of: Annotated[datetime | None, BeforeValidator(_instant)] = Field(
        default=None,
        description=(
            "Read the service as it stood at this UTC instant, no earlier than its archive's "
            "start on 2020-11-25 and not in the future, so pages cannot drift; the live "
            "service by default."
        ),
    )

    @model_validator(mode="after")
    def _well_formed(self) -> DamageFilters:
        if self.office is not None:
            self.office = [_office(value) for value in self.office]
        if self.efscale is not None:
            self.efscale = list(dict.fromkeys(_rating(value) for value in self.efscale))
        if self.as_of is not None:
            self.as_of = as_utc(self.as_of)
        return self


class DamageSurveysParams(DamageFilters):
    """A damage survey query names its layer, then any filter."""

    layer: Annotated[str, choice("points", "lines", "polygons")] = Field(
        description=(
            "Required layer: points (rated damage points), lines (tornado tracks), or "
            "polygons (damage areas)."
        )
    )

    @model_validator(mode="after")
    def _office_needs_a_field(self) -> DamageSurveysParams:
        if self.office is not None and LAYERS[self.layer].office_field is None:
            raise ValueError(
                "office is not recorded on polygons; select polygons by bbox, or ask for points "
                "or lines"
            )
        return self


def _offices(field: str, codes: list[str]) -> str:
    """Features surveyed by any of ``codes``, where a track may list several offices."""
    terms = []
    for code in codes:
        column = f"UPPER({field})"
        terms.append(
            f"({column} = '{code}' OR {column} LIKE '{code},%' OR "
            f"{column} LIKE '%,{code}' OR {column} LIKE '%,{code},%')"
        )
    return terms[0] if len(terms) == 1 else "(" + " OR ".join(terms) + ")"


def _where(layer: Layer, params: DamageFilters, start: datetime, end: datetime) -> str:
    """The SQL ``where`` a window and filters select, inclusive at both ends of the window."""
    field = layer.time_field
    window = f"{field} >= {arcgis.timestamp(start)} AND {field} <= {arcgis.timestamp(end)}"
    terms = [f"(({window}) OR {field} IS NULL)" if params.include_undated else window]
    if params.office is not None and layer.office_field is not None:
        terms.append(_offices(layer.office_field, params.office))
    if params.efscale is not None:
        terms.append("efscale IN (" + ", ".join(arcgis.literal(v) for v in params.efscale) + ")")
    return " AND ".join(terms)


class _DamageToolkit(HttpProvider):
    """What both datasets share: validating a query and asking the layer for its ids."""

    def _window(self, query: Query) -> tuple[datetime, datetime]:
        self.reject(
            query,
            "text",
            "variables",
            hint="the attributes are fixed; select columns locally after opening",
        )
        return self.utc_window(query)

    def _selection(
        self, layer: Layer, params: DamageFilters, query: Query, start: datetime, end: datetime
    ) -> tuple[arcgis.LayerInfo, str, list[int]]:
        info = arcgis.layer_info(layer.url, self._http())
        if params.as_of is not None:
            self._check_moment(params.as_of, info)
        where = _where(layer, params, start, end)
        ids = arcgis.object_ids(
            layer.url, self._http(), where, bbox=query.bbox, moment=params.as_of
        )
        return info, where, ids

    def _check_moment(self, moment: datetime, info: arcgis.LayerInfo) -> None:
        if moment > datetime.now(UTC):
            raise QueryError(f"{self.dataset.id} as_of {moment:%Y-%m-%dT%H:%MZ} is in the future")
        if info.archive_start is None:
            raise QueryError(f"{self.dataset.id} keeps no archive now, so as_of cannot be read")
        if moment < info.archive_start:
            raise QueryError(
                f"{self.dataset.id} as_of {moment:%Y-%m-%dT%H:%MZ} is before the service's "
                f"archive begins at {info.archive_start:%Y-%m-%dT%H:%M:%SZ}, where it would "
                "silently answer with nothing"
            )


class NwsDamageSurveys(_DamageToolkit):
    """One layer's damage survey features in a window, as GeoJSON pages of object-id ranges."""

    params_model = DamageSurveysParams

    def list_assets(self, query: Query) -> list[Asset]:
        """One GeoJSON asset per run of at most the layer's record limit of matching features."""
        params = self.parse_params(query, DamageSurveysParams)
        start, end = self._window(query)
        layer = LAYERS[params.layer]
        info, where, ids = self._selection(layer, params, query, start, end)
        window = TimeRange(start=start, end=end)
        properties = {"layer": params.layer}
        if params.as_of is not None:
            properties["as_of"] = params.as_of.isoformat().replace("+00:00", "Z")
        assets = []
        for first, last in arcgis.id_ranges(ids, info.max_record_count):
            href = arcgis.query_url(
                layer.url,
                f"{where} AND {arcgis.id_range(OBJECT_ID, first, last)}",
                bbox=query.bbox,
                order_by=OBJECT_ID,
                moment=params.as_of,
            )
            digest = _digest(href)
            assets.append(
                Asset(
                    id=f"nws_damage_{params.layer}_{start:%Y%m%d}_{end:%Y%m%d}_"
                    f"{first}-{last}_{digest}.geojson",
                    dataset_id=self.dataset.id,
                    href=href,
                    protocol=Protocol.HTTP,
                    media_type="application/geo+json",
                    time=window,
                    bbox=query.bbox,
                    properties=properties,
                )
            )
        return assets

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download one page, refusing an error body or a page the service cut short."""
        http.download(asset.href, dest, self._http())
        try:
            arcgis.check_feature_collection(dest)
        except BaseException:
            dest.unlink(missing_ok=True)
            raise
        return dest


class NwsDamagePhotos(_DamageToolkit):
    """Each image attached to a damage point in a window, one asset per file."""

    params_model = DamageFilters

    def list_assets(self, query: Query) -> list[Asset]:
        """One asset per JPEG or PNG attachment of the matching damage points."""
        params = self.parse_params(query, DamageFilters)
        start, end = self._window(query)
        if end - start > MAX_WINDOW:
            raise QueryError(
                f"{self.dataset.id} windows span at most 7 days, since listing asks for every "
                "point's attachments; split longer intervals"
            )
        layer = LAYERS["points"]
        info, where, ids = self._selection(layer, params, query, start, end)
        points: dict[int, dict[str, Any]] = {}
        for first, last in arcgis.id_ranges(ids, info.max_record_count):
            for feature in arcgis.query_features(
                layer.url,
                self._http(),
                f"{where} AND {arcgis.id_range(OBJECT_ID, first, last)}",
                out_fields=(OBJECT_ID, "globalid", layer.time_field, "efscale"),
                bbox=query.bbox,
                moment=params.as_of,
                order_by=OBJECT_ID,
            ):
                points[int(feature["attributes"][OBJECT_ID])] = feature
        attachments = arcgis.query_attachments(
            layer.url,
            self._http(),
            sorted(points),
            max_records=info.max_record_count,
            moment=params.as_of,
        )
        return [
            self._photo(attachment, points[attachment.parent_id], layer)
            for attachment in attachments
            if attachment.content_type in PHOTO_TYPES and attachment.parent_id in points
        ]

    def _photo(self, attachment: arcgis.Attachment, point: dict[str, Any], layer: Layer) -> Asset:
        attributes = point["attributes"]
        try:
            when = arcgis.from_epoch_ms(attributes.get(layer.time_field))
        except ValueError as error:
            raise httpx.DecodingError(f"point {attachment.parent_id}: {error}") from error
        box = _point_box(point.get("geometry"))
        properties = {"point_objectid": str(attachment.parent_id), "name": attachment.name}
        if attachment.parent_global_id:
            properties["point_globalid"] = attachment.parent_global_id
        if isinstance(attributes.get("efscale"), str) and attributes["efscale"]:
            properties["efscale"] = attributes["efscale"]
        suffix = PHOTO_TYPES[attachment.content_type]
        return Asset(
            id=f"nws_damage_photo_{attachment.parent_id}_{attachment.id}{suffix}",
            dataset_id=self.dataset.id,
            href=attachment.url,
            protocol=Protocol.HTTP,
            media_type=attachment.content_type,
            size=attachment.size,
            time=None if when is None else TimeRange(start=when, end=when),
            bbox=box,
            properties=properties,
        )

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download one attachment, refusing a body whose size is not the one listed."""
        http.download(asset.href, dest, self._http())
        if asset.size is not None and dest.stat().st_size != asset.size:
            written = dest.stat().st_size
            dest.unlink(missing_ok=True)
            raise httpx.DecodingError(
                f"{asset.id} arrived as {written} bytes where the listing gave {asset.size}"
            )
        return dest


def _point_box(geometry: object) -> BBox | None:
    """A point geometry as a box of no extent, or None when it is missing or off the globe."""
    if not isinstance(geometry, dict):
        return None
    x, y = geometry.get("x"), geometry.get("y")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    if not (-180 <= x <= 180 and -90 <= y <= 90):
        return None
    return BBox(west=x, south=y, east=x, north=y)


def _digest(href: str) -> str:
    return hashlib.sha256(href.encode()).hexdigest()[:12]
