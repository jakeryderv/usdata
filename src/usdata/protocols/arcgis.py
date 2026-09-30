"""ArcGIS REST feature-layer queries, object-id pages, and attachments over HTTP.

A FeatureServer layer answers ``/query`` with a SQL ``where`` clause, an optional
envelope, and an output format, and returns at most its ``maxRecordCount``
features per response, flagging a cut-short one with ``exceededTransferLimit``.
It can list every matching object id in one response, which is what makes pages
that do not depend on offsets possible: sort the ids, cut them into runs of at
most ``maxRecordCount``, and ask for each run by its first and last id.

The service reports its own failures as HTTP 200 with an ``error`` body, so every
JSON answer is checked for one. This module builds the requests and reads the
answers; which layer, fields, and filters mean what is the adapter's business.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from usdata.models import BBox
from usdata.protocols import http

WGS84 = "4326"
"""The spatial reference every envelope is given in and every geometry is asked for."""

ATTACHMENT_BATCH = 100
"""Features per ``queryAttachments`` request; their ids ride in the URL."""

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class ServiceError(httpx.RequestError):
    """The service answered with an ArcGIS ``error`` body, whatever its HTTP status.

    ArcGIS reports its own failures as HTTP 200, so the status alone would let one
    through as data. It is not retried: the shared policy retries transport
    failures and 5xx statuses, and this is neither.
    """


@dataclass(frozen=True)
class LayerInfo:
    """What one layer's metadata says about how it can be queried."""

    max_record_count: int
    object_id_field: str
    fields: frozenset[str]
    formats: frozenset[str]
    """``supportedQueryFormats``, lowercased, such as ``json`` and ``geojson``."""
    has_attachments: bool
    query_attachments: bool
    """Whether ``queryAttachments`` answers for many features in one request."""
    archive_start: datetime | None
    """The first instant ``historicMoment`` can read, or None for an unarchived layer."""


@dataclass(frozen=True)
class Attachment:
    """One file attached to one feature, as the attachment listing describes it."""

    layer: str
    parent_id: int
    parent_global_id: str | None
    id: int
    global_id: str | None
    name: str
    content_type: str
    size: int

    @property
    def url(self) -> str:
        """Where the file's bytes are served."""
        return attachment_url(self.layer, self.parent_id, self.id)


def _layer(url: str) -> str:
    parts = urlsplit(url)
    last = parts.path.rstrip("/").rsplit("/", 1)[-1]
    if parts.scheme != "https" or not parts.netloc or parts.query or parts.fragment:
        raise ValueError("an ArcGIS layer must be an HTTPS URL without query or fragment")
    if not last.isascii() or not last.isdigit():
        raise ValueError(f"an ArcGIS layer URL ends in the layer's number, not {last!r}")
    return url.rstrip("/")


def epoch_ms(value: datetime) -> str:
    """An aware instant as the milliseconds since 1970 that ArcGIS dates are counted in."""
    if value.tzinfo is None:
        raise ValueError("ArcGIS instants must have a timezone")
    return str((value - _EPOCH) // timedelta(milliseconds=1))


def from_epoch_ms(value: object) -> datetime | None:
    """An ArcGIS date attribute as an aware UTC instant, or None when it is null."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"an ArcGIS date is whole milliseconds, not {value!r}")
    return _EPOCH + timedelta(milliseconds=value)


def timestamp(value: datetime) -> str:
    """An aware instant as a SQL ``TIMESTAMP`` literal in UTC, to the millisecond."""
    if value.tzinfo is None:
        raise ValueError("ArcGIS instants must have a timezone")
    stamp = value.astimezone(UTC)
    return f"TIMESTAMP '{stamp:%Y-%m-%d %H:%M:%S}.{stamp.microsecond // 1000:03d}'"


def literal(value: str) -> str:
    """A SQL string literal, with any quote inside it doubled."""
    return "'" + value.replace("'", "''") + "'"


def id_range(field: str, first: int, last: int) -> str:
    """Object ids from ``first`` to ``last`` inclusive, as a ``where`` term."""
    return f"{field} >= {first} AND {field} <= {last}"


def id_ranges(ids: Iterable[int], size: int) -> list[tuple[int, int]]:
    """Sorted distinct ids cut into runs of at most ``size``, each as its first and last id."""
    if size < 1:
        raise ValueError("a page holds at least one feature")
    ordered = sorted(set(ids))
    return [
        (run[0], run[-1]) for run in (ordered[i : i + size] for i in range(0, len(ordered), size))
    ]


def _envelope(bbox: BBox) -> dict[str, str]:
    return {
        "geometry": ",".join(f"{value:.12g}" for value in bbox.as_tuple()),
        "geometryType": "esriGeometryEnvelope",
        "inSR": WGS84,
        "spatialRel": "esriSpatialRelIntersects",
    }


def query_params(
    where: str,
    *,
    bbox: BBox | None = None,
    out_fields: Sequence[str] = ("*",),
    order_by: str | None = None,
    moment: datetime | None = None,
    fmt: str = "geojson",
) -> dict[str, str]:
    """The parameters of one ``/query`` request, always in the same order.

    Args:
        where: A SQL ``where`` clause over the layer's fields.
        bbox: An envelope the features must intersect, in WGS84 degrees.
        out_fields: Attribute fields to return; ``*`` for all of them.
        order_by: ``orderByFields``, such as ``objectid``.
        moment: Read the layer as it stood at this instant (``historicMoment``).
        fmt: ``geojson`` or ``json``.
    """
    params = {"where": where}
    if bbox is not None:
        params.update(_envelope(bbox))
    params["outFields"] = ",".join(out_fields)
    params["outSR"] = WGS84
    if order_by is not None:
        params["orderByFields"] = order_by
    if moment is not None:
        params["historicMoment"] = epoch_ms(moment)
    params["f"] = fmt
    return params


def query_url(
    layer: str,
    where: str,
    *,
    bbox: BBox | None = None,
    out_fields: Sequence[str] = ("*",),
    order_by: str | None = None,
    moment: datetime | None = None,
    fmt: str = "geojson",
) -> str:
    """The full URL of one ``/query`` request; see ``query_params``."""
    params = query_params(
        where, bbox=bbox, out_fields=out_fields, order_by=order_by, moment=moment, fmt=fmt
    )
    return str(httpx.URL(f"{_layer(layer)}/query", params=params))


def get_json(url: str, client: httpx.Client, params: dict[str, str] | None = None) -> Any:
    """GET a JSON answer with the shared retries, refusing an ArcGIS ``error`` body."""
    response = http.get(url, client, params=params)
    try:
        body = response.json()
    except ValueError as error:
        raise httpx.DecodingError(
            f"ArcGIS answered with something other than JSON: {response.text[:200]!r}",
            request=response.request,
        ) from error
    if isinstance(body, dict) and "error" in body:
        raise ServiceError(f"ArcGIS error: {_error_text(body['error'])}", request=response.request)
    if not isinstance(body, dict):
        raise httpx.DecodingError("ArcGIS answered with a JSON value that is not an object")
    return body


def _error_text(error: object) -> str:
    if not isinstance(error, dict):
        return repr(error)
    details = error.get("details") or []
    extra = "; ".join(str(item) for item in details if item) if isinstance(details, list) else ""
    message = f"{error.get('code', '?')} {error.get('message', '')}".strip()
    return f"{message} ({extra})" if extra else message


def layer_info(layer: str, client: httpx.Client) -> LayerInfo:
    """Read the paging limit, fields, formats, attachment support, and archive start."""
    url = _layer(layer)
    body = get_json(url, client, params={"f": "json"})
    try:
        count = body["maxRecordCount"]
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("maxRecordCount must be a positive integer")
        advanced = body.get("advancedQueryCapabilities") or {}
        archiving = body.get("archivingInfo") or {}
        start = archiving.get("startArchivingMoment")
        return LayerInfo(
            max_record_count=count,
            object_id_field=str(body["objectIdField"]),
            fields=frozenset(str(field["name"]) for field in body.get("fields") or []),
            formats=frozenset(
                part.strip().lower()
                for part in str(body.get("supportedQueryFormats", "")).split(",")
            )
            - {""},
            has_attachments=body.get("hasAttachments") is True,
            query_attachments=advanced.get("supportsQueryAttachments") is True,
            archive_start=from_epoch_ms(start)
            if archiving.get("supportsQueryWithHistoricMoment")
            else None,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise httpx.DecodingError(f"invalid ArcGIS layer description at {url}") from error


def object_ids(
    layer: str,
    client: httpx.Client,
    where: str,
    *,
    bbox: BBox | None = None,
    moment: datetime | None = None,
) -> list[int]:
    """Every object id matching the filters, sorted; the service does not page this answer."""
    params = query_params(where, bbox=bbox, moment=moment, fmt="json")
    del params["outFields"], params["outSR"]
    params["returnIdsOnly"] = "true"
    body = get_json(f"{_layer(layer)}/query", client, params=params)
    ids = body.get("objectIds")
    if ids is None:  # ArcGIS writes null, not [], when nothing matches.
        return []
    if not isinstance(ids, list) or any(
        isinstance(value, bool) or not isinstance(value, int) for value in ids
    ):
        raise httpx.DecodingError("ArcGIS object ids must be a list of integers")
    return sorted(set(ids))


def query_features(
    layer: str,
    client: httpx.Client,
    where: str,
    *,
    out_fields: Sequence[str],
    bbox: BBox | None = None,
    moment: datetime | None = None,
    order_by: str | None = None,
) -> list[dict[str, Any]]:
    """One page of features as Esri JSON, refusing a page the service cut short."""
    params = query_params(
        where, bbox=bbox, out_fields=out_fields, order_by=order_by, moment=moment, fmt="json"
    )
    body = get_json(f"{_layer(layer)}/query", client, params=params)
    if body.get("exceededTransferLimit"):
        raise httpx.DecodingError("ArcGIS cut a page short; ask for fewer features at once")
    features = body.get("features")
    if not isinstance(features, list) or not all(
        isinstance(item, dict) and isinstance(item.get("attributes"), dict) for item in features
    ):
        raise httpx.DecodingError("ArcGIS features must be a list of objects with attributes")
    return features


def attachment_url(layer: str, object_id: int, attachment_id: int) -> str:
    """Where one attachment's bytes are served."""
    return f"{_layer(layer)}/{int(object_id)}/attachments/{int(attachment_id)}"


def _attachment(layer: str, parent: int, parent_global: object, info: object) -> Attachment:
    if not isinstance(info, dict):
        raise ValueError("an attachment must be an object")
    for key in ("id", "size"):
        if isinstance(info.get(key), bool) or not isinstance(info.get(key), int):
            raise ValueError(f"attachment {key} must be an integer")
    return Attachment(
        layer=layer,
        parent_id=parent,
        parent_global_id=parent_global if isinstance(parent_global, str) else None,
        id=info["id"],
        global_id=info.get("globalId") if isinstance(info.get("globalId"), str) else None,
        name=str(info.get("name") or ""),
        content_type=str(info.get("contentType") or ""),
        size=info["size"],
    )


def feature_attachments(layer: str, object_id: int, client: httpx.Client) -> list[Attachment]:
    """The attachments of one feature, from its own ``/attachments`` listing."""
    url = _layer(layer)
    body = get_json(f"{url}/{int(object_id)}/attachments", client, params={"f": "json"})
    try:
        infos = body["attachmentInfos"]
        if not isinstance(infos, list):
            raise ValueError("attachmentInfos must be a list")
        return [_attachment(url, int(object_id), None, info) for info in infos]
    except (KeyError, TypeError, ValueError) as error:
        raise httpx.DecodingError(f"invalid ArcGIS attachment listing: {error}") from error


def query_attachments(
    layer: str,
    client: httpx.Client,
    ids: Sequence[int],
    *,
    max_records: int,
    moment: datetime | None = None,
    batch: int = ATTACHMENT_BATCH,
) -> list[Attachment]:
    """The attachments of many features, ``batch`` features per ``queryAttachments`` request.

    The service stops at ``max_records`` attachments per answer and says nothing
    when it does, so an answer that reaches the limit is asked again in halves
    until every answer falls short of it.

    Raises:
        httpx.DecodingError: One feature alone holds ``max_records`` attachments or more.
    """
    url = _layer(layer)
    found: list[Attachment] = []
    pending = [list(ids[i : i + batch]) for i in range(0, len(ids), batch)]
    while pending:
        group = pending.pop(0)
        params = {"objectIds": ",".join(str(int(value)) for value in group), "f": "json"}
        if moment is not None:
            params["historicMoment"] = epoch_ms(moment)
        body = get_json(f"{url}/queryAttachments", client, params=params)
        try:
            groups = body["attachmentGroups"]
            if not isinstance(groups, list):
                raise ValueError("attachmentGroups must be a list")
            answer = [
                _attachment(url, int(item["parentObjectId"]), item.get("parentGlobalId"), info)
                for item in groups
                for info in item["attachmentInfos"]
            ]
        except (KeyError, TypeError, ValueError) as error:
            raise httpx.DecodingError(f"invalid ArcGIS attachment query: {error}") from error
        if len(answer) >= max_records:
            if len(group) == 1:
                raise httpx.DecodingError(
                    f"feature {group[0]} holds at least {max_records} attachments, more than "
                    "one answer can say"
                )
            half = len(group) // 2
            pending[:0] = [group[:half], group[half:]]
            continue
        found.extend(answer)
    return sorted(found, key=lambda item: (item.parent_id, item.id))


def check_feature_collection(path: Path) -> None:
    """Refuse a downloaded GeoJSON page that is an error body or was cut short.

    Raises:
        ServiceError: The file holds an ArcGIS ``error`` body.
        httpx.DecodingError: It is not a FeatureCollection, or the service truncated it.
    """
    try:
        body = json.loads(path.read_bytes())
    except (OSError, ValueError) as error:
        raise httpx.DecodingError(f"{path.name} is not JSON") from error
    if isinstance(body, dict) and "error" in body:
        raise ServiceError(f"ArcGIS error: {_error_text(body['error'])}")
    if not isinstance(body, dict) or body.get("type") != "FeatureCollection":
        raise httpx.DecodingError(f"{path.name} is not a GeoJSON FeatureCollection")
    properties = body.get("properties")
    if isinstance(properties, dict) and properties.get("exceededTransferLimit"):
        raise httpx.DecodingError(
            f"{path.name} was cut short by the service's record limit; list the query again"
        )
