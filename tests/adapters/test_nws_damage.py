"""NWS Damage Assessment Toolkit: validation, the where clause, object-id pages, photos, fetch."""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

from usdata import build_query, get
from usdata.models import Query
from usdata.protocols import arcgis
from usdata.providers.base import QueryError
from usdata.providers.noaa.nws_damage import (
    SERVICE_URL,
    DamageSurveysParams,
    NwsDamagePhotos,
    NwsDamageSurveys,
)

POINTS, LINES, POLYGONS = (f"{SERVICE_URL}/{number}" for number in range(3))
ARCHIVE_START = 1606331043000  # 2020-11-25T19:04:03Z, when the lines layer's archive begins.
WINDOW = "TIMESTAMP '2024-05-06 12:00:00.000' AND {field} <= TIMESTAMP '2024-05-07 12:00:00.000'"


def info(max_records: int = 2000) -> dict:
    return {
        "maxRecordCount": max_records,
        "objectIdField": "objectid",
        "fields": [{"name": "objectid"}],
        "supportedQueryFormats": "JSON, geoJSON, PBF",
        "hasAttachments": True,
        "advancedQueryCapabilities": {"supportsQueryAttachments": True},
        "archivingInfo": {
            "supportsQueryWithHistoricMoment": True,
            "startArchivingMoment": ARCHIVE_START,
        },
    }


def surveys() -> NwsDamageSurveys:
    return NwsDamageSurveys(get("noaa:nws-damage-surveys"))


def photos() -> NwsDamagePhotos:
    return NwsDamagePhotos(get("noaa:nws-damage-photos"))


def query(**kwargs) -> Query:
    return build_query(**{"start": "2024-05-06T12:00Z", "end": "2024-05-07T12:00Z", **kwargs})


def layer(mock: respx.MockRouter, url: str, ids: list[int] | None, max_records: int = 2000):
    """Answer a layer's metadata and its id listing; return the id listing's route."""
    mock.get(url, params={"f": "json"}).respond(200, json=info(max_records))
    return mock.get(f"{url}/query", params={"returnIdsOnly": "true"}).respond(
        200, json={"objectIdFieldName": "objectid", "objectIds": ids}
    )


def listed(url: str = LINES, ids: list[int] | None = None, **kwargs) -> tuple[str, list]:
    """The ``where`` a surveys query sends for its ids, and the assets it lists."""
    with surveys() as provider, respx.mock() as mock:
        route = layer(mock, url, [7] if ids is None else ids)
        assets = provider.list_assets(query(**kwargs))
    return route.calls[0].request.url.params["where"], assets


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"layer": "tracks"},
        {"layer": "lines", "start": None, "end": None},
        {"layer": "lines", "end": None},
        {"layer": "lines", "text": "tornado"},
        {"layer": "lines", "variables": ["efscale"]},
        {"layer": "polygons", "office": "TSA"},
        {"layer": "lines", "office": "TULSA"},
        {"layer": "lines", "office": "T1A"},
        {"layer": "lines", "office": ""},
        {"layer": "lines", "efscale": "EF6"},
        {"layer": "lines", "efscale": "EF4' OR '1'='1"},
        {"layer": "lines", "include_undated": "yes"},
        {"layer": "lines", "as_of": 1715126400},
        {"layer": "lines", "as_of": "yesterday"},
        {"layer": "lines", "typo": 1},
    ],
)
def test_bad_survey_queries_fail_before_network(kwargs) -> None:
    with surveys() as provider, pytest.raises(QueryError), respx.mock() as mock:
        provider.list_assets(query(**kwargs))
    assert not mock.calls


@pytest.mark.parametrize(
    "kwargs",
    [
        {"layer": "lines"},
        {"start": "2024-05-01", "end": "2024-05-08T00:00:01Z"},
        {"office": "OUN,TULSA"},
        {"variables": ["image"]},
    ],
)
def test_bad_photo_queries_fail_before_network(kwargs) -> None:
    with photos() as provider, pytest.raises(QueryError), respx.mock() as mock:
        provider.list_assets(query(**kwargs))
    assert not mock.calls


def message(**params: object) -> str:
    with surveys() as provider, pytest.raises(QueryError) as raised:
        provider.parse_params(Query(params=params), DamageSurveysParams)
    return str(raised.value)


def test_refusals_say_what_to_do_instead() -> None:
    assert message() == (
        "layer is required: layer: points (rated damage points), lines (tornado tracks), or "
        "polygons (damage areas)"
    )
    assert "layer must be points, lines, or polygons" in message(layer="tracks")
    assert "office is not recorded on polygons; select polygons by bbox" in message(
        layer="polygons", office="TSA"
    )
    assert "three-letter NWS office code such as TSA" in message(layer="lines", office="TULSA")
    assert "must be one of EF0, EF1" in message(layer="lines", efscale="EF6")
    assert "as_of must be a UTC timestamp" in message(layer="lines", as_of=1715126400)
    with photos() as provider, pytest.raises(QueryError, match="at most 7 days"):
        provider.list_assets(query(end="2024-05-13T12:00:01Z"))


def test_a_window_selects_by_storm_time_inclusive_at_both_ends() -> None:
    where, (asset,) = listed(layer="lines")
    assert where == "starttime >= " + WINDOW.format(field="starttime")
    where, _ = listed(POINTS, layer="points")
    assert where == "stormdate >= " + WINDOW.format(field="stormdate")
    where, _ = listed(POLYGONS, layer="polygons")
    assert where.startswith("stormdate >= TIMESTAMP")
    # Naive, offset, and date-only bounds all resolve to UTC, a bare end date to its last instant.
    where, _ = listed(layer="lines", start="2011-04-27", end="2011-04-27")
    assert where == (
        "starttime >= TIMESTAMP '2011-04-27 00:00:00.000' AND "
        "starttime <= TIMESTAMP '2011-04-27 23:59:59.999'"
    )
    assert asset.time is not None and asset.time.start == datetime(2024, 5, 6, 12, tzinfo=UTC)


def test_undated_features_are_left_out_unless_asked_for() -> None:
    assert "IS NULL" not in listed(POINTS, layer="points")[0]
    for value in (True, "true", "TRUE"):
        where, _ = listed(POINTS, layer="points", include_undated=value)
        assert (
            where
            == "((stormdate >= " + WINDOW.format(field="stormdate") + ") OR stormdate IS NULL)"
        )


def test_offices_match_a_track_shared_by_several_and_ratings_use_the_toolkits_spelling() -> None:
    where, _ = listed(layer="lines", office="tsa,OUN", efscale="ef4,Tstm/wind,EF4")
    one = (
        "(UPPER(wfo) = '{0}' OR UPPER(wfo) LIKE '{0},%' OR "
        "UPPER(wfo) LIKE '%,{0}' OR UPPER(wfo) LIKE '%,{0},%')"
    )
    assert where.endswith(
        f" AND ({one.format('TSA')} OR {one.format('OUN')}) AND efscale IN ('EF4', 'TSTM/Wind')"
    )
    where, _ = listed(POINTS, layer="points", office="meg")
    assert where.endswith(" AND " + one.replace("wfo", "office").format("MEG"))


def test_pages_are_object_id_runs_no_longer_than_the_layers_limit() -> None:
    ids = [*range(1, 4001), 9000, 9001]
    with surveys() as provider, respx.mock() as mock:
        layer(mock, POINTS, list(reversed(ids)), max_records=2000)
        box = (-97.5, 35.0, -96.0, 36.5)
        assets = provider.list_assets(query(layer="points", bbox=box))
        again = provider.list_assets(query(layer="points", bbox=box))
    assert assets == again
    assert [a.id.split("_")[5] for a in assets] == ["1-2000", "2001-4000", "9000-9001"]
    first = httpx.URL(assets[0].href)
    assert first.params["where"].endswith(" AND objectid >= 1 AND objectid <= 2000")
    assert first.params["orderByFields"] == "objectid" and first.params["f"] == "geojson"
    assert first.params["geometry"] == "-97.5,35,-96,36.5" and first.params["inSR"] == "4326"
    assert "historicMoment" not in first.params
    assert all(a.id.startswith("nws_damage_points_20240506_20240507_") for a in assets)
    assert all(a.id.endswith(".geojson") and a.media_type == "application/geo+json" for a in assets)
    assert all(a.properties == {"layer": "points"} for a in assets)
    assert all(a.bbox is not None and a.bbox.west == -97.5 for a in assets)


def test_nothing_matching_lists_nothing() -> None:
    assert listed(ids=[], layer="lines")[1] == []
    with surveys() as provider, respx.mock() as mock:
        mock.get(LINES, params={"f": "json"}).respond(200, json=info())
        mock.get(f"{LINES}/query").respond(200, json={"objectIds": None})
        assert provider.list_assets(query(layer="lines")) == []


def test_as_of_reads_the_archive_and_is_recorded_on_every_page() -> None:
    _, (asset,) = listed(layer="lines", as_of="2024-05-08T00:00Z")
    assert httpx.URL(asset.href).params["historicMoment"] == "1715126400000"
    assert asset.properties == {"layer": "lines", "as_of": "2024-05-08T00:00:00Z"}
    assert asset.id != listed(layer="lines")[1][0].id
    with surveys() as provider, respx.mock() as mock:
        route = layer(mock, LINES, [7])
        provider.list_assets(query(layer="lines", as_of="2024-05-08T00:00Z"))
    assert route.calls[0].request.url.params["historicMoment"] == "1715126400000"


@pytest.mark.parametrize(
    ("as_of", "match"),
    [
        ("2020-11-25T19:04:02Z", "before the service's archive begins at 2020-11-25T19:04:03Z"),
        ("2100-01-01T00:00Z", "is in the future"),
    ],
)
def test_an_as_of_the_archive_cannot_answer_is_refused(as_of: str, match: str) -> None:
    with surveys() as provider, respx.mock(assert_all_called=False) as mock:
        route = layer(mock, LINES, [7])
        with pytest.raises(QueryError, match=match):
            provider.list_assets(query(layer="lines", as_of=as_of))
        assert not route.called  # Only the layer's metadata was read.


def test_a_layer_without_an_archive_refuses_as_of() -> None:
    body = {k: v for k, v in info().items() if k != "archivingInfo"}
    with surveys() as provider, respx.mock() as mock, pytest.raises(QueryError, match="no archive"):
        mock.get(LINES).respond(200, json=body)
        provider.list_assets(query(layer="lines", as_of="2024-05-08T00:00Z"))


@pytest.mark.l2
def test_a_page_is_fetched_as_served_and_a_bad_one_leaves_no_file(tmp_path: Path) -> None:
    _, (asset,) = listed(layer="lines")
    good = b'{"type":"FeatureCollection","features":[{"type":"Feature","id":7}]}'
    error = b'{"error":{"code":500,"message":"Error performing query operation","details":[]}}'
    cut = b'{"type":"FeatureCollection","features":[],"properties":{"exceededTransferLimit":true}}'
    dest = tmp_path / asset.id
    with surveys() as provider, respx.mock() as mock:
        route = mock.get(asset.href).respond(200, content=good)
        assert provider.fetch(asset, dest) == dest
        assert dest.read_bytes() == good
        dest.unlink()
        route.respond(200, content=error)
        with pytest.raises(arcgis.ServiceError, match="Error performing query"):
            provider.fetch(asset, dest)
        assert not dest.exists()
        route.respond(200, content=cut)
        with pytest.raises(httpx.DecodingError, match="cut short"):
            provider.fetch(asset, dest)
        assert list(tmp_path.iterdir()) == []


def point(oid: int, stormdate: int | None, efscale: str | None = "EF4") -> dict:
    attributes = {"objectid": oid, "globalid": f"{{P{oid}}}", "stormdate": stormdate}
    attributes["efscale"] = efscale
    return {"attributes": attributes, "geometry": {"x": -96.3, "y": 36.4}}


def group(oid: int, *infos: tuple[int, str, str, int]) -> dict:
    return {
        "parentObjectId": oid,
        "parentGlobalId": f"{{P{oid}}}",
        "attachmentInfos": [
            {"id": aid, "globalId": f"{{A{aid}}}", "name": name, "contentType": kind, "size": size}
            for aid, name, kind, size in infos
        ],
    }


def photo_listing(**kwargs) -> tuple[list, list[httpx.Request]]:
    with photos() as provider, respx.mock() as mock:
        layer(mock, POINTS, [30, 10, 20])
        mock.get(f"{POINTS}/query", params={"f": "json"}).respond(
            200,
            json={
                "features": [
                    point(10, 1715047920000),
                    point(20, None, efscale=None),
                    point(30, 1715048000000, efscale="EF2"),
                ]
            },
        )
        mock.get(f"{POINTS}/queryAttachments").respond(
            200,
            json={
                "attachmentGroups": [
                    group(30, (301, "b.png", "image/png", 50)),
                    group(
                        10,
                        (102, "a.jpg", "image/jpeg", 5009),
                        (101, "a.jpg", "image/jpeg", 677271),
                        (103, "notes.pdf", "application/pdf", 900),
                    ),
                    group(20, (201, "c.jpg", "image/jpeg", 40)),
                ]
            },
        )
        assets = provider.list_assets(query(**kwargs))
        requests = [call.request for call in mock.calls]
    return assets, requests


def test_each_image_attached_to_a_matching_point_is_one_asset() -> None:
    assets, requests = photo_listing(bbox=(-97.0, 36.0, -96.0, 37.0))
    assert [a.id for a in assets] == [
        "nws_damage_photo_10_101.jpg",
        "nws_damage_photo_10_102.jpg",
        "nws_damage_photo_20_201.jpg",
        "nws_damage_photo_30_301.png",
    ]
    first = assets[0]
    assert first.href == f"{POINTS}/10/attachments/101"
    assert first.media_type == "image/jpeg" and first.size == 677271
    assert first.time is not None and first.time.start == datetime(2024, 5, 7, 2, 12, tzinfo=UTC)
    assert first.bbox is not None and (first.bbox.west, first.bbox.south) == (-96.3, 36.4)
    assert first.properties == {
        "point_objectid": "10",
        "name": "a.jpg",
        "point_globalid": "{P10}",
        "efscale": "EF4",
    }
    # The same-name thumbnail is kept, as served; a PDF is not a photo.
    assert assets[1].size == 5009 and assets[1].properties["name"] == "a.jpg"
    assert assets[2].time is None and "efscale" not in assets[2].properties
    assert assets[3].media_type == "image/png"
    features = next(
        request
        for request in requests
        if request.url.path.endswith("/query") and "outFields" in request.url.params
    )
    assert features.url.params["outFields"] == "objectid,globalid,stormdate,efscale"
    assert features.url.params["geometry"] == "-97,36,-96,37"
    assert features.url.params["where"].endswith(" AND objectid >= 10 AND objectid <= 30")
    attachments = next(r for r in requests if r.url.path.endswith("/queryAttachments"))
    assert attachments.url.params["objectIds"] == "10,20,30"


def test_no_points_means_no_attachment_requests() -> None:
    with photos() as provider, respx.mock() as mock:
        layer(mock, POINTS, None)
        assert provider.list_assets(query()) == []
        assert len(mock.calls) == 2


@pytest.mark.l2
def test_a_photo_whose_size_is_not_the_listed_one_leaves_no_file(tmp_path: Path) -> None:
    assets, _ = photo_listing()
    asset = assets[2]  # 40 bytes, as listed.
    dest = tmp_path / asset.id
    with photos() as provider, respx.mock() as mock:
        route = mock.get(asset.href).respond(200, content=b"\xff\xd8" + b"x" * 38)
        assert provider.fetch(asset, dest) == dest and dest.stat().st_size == 40
        dest.unlink()
        route.respond(200, content=json.dumps({"error": {"code": 404}}).encode())
        with pytest.raises(
            httpx.DecodingError, match="arrived as 24 bytes where the listing gave 40"
        ):
            provider.fetch(asset, dest)
    assert list(tmp_path.iterdir()) == []
