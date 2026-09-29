import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import respx

from usdata.models import BBox
from usdata.protocols import arcgis, http

LAYER = "https://example.test/arcgis/rest/services/demo/FeatureServer/0"
INFO = {
    "maxRecordCount": 2000,
    "objectIdField": "objectid",
    "fields": [{"name": "objectid"}, {"name": "stormdate"}],
    "supportedQueryFormats": "JSON, geoJSON, PBF",
    "hasAttachments": True,
    "advancedQueryCapabilities": {"supportsQueryAttachments": True},
    "archivingInfo": {
        "supportsQueryWithHistoricMoment": True,
        "startArchivingMoment": 1606326869000,
    },
}


def test_timestamps_are_utc_to_the_millisecond() -> None:
    central = timezone(timedelta(hours=-5))
    assert arcgis.timestamp(datetime(2024, 5, 6, 21, 12, 0, 500999, tzinfo=central)) == (
        "TIMESTAMP '2024-05-07 02:12:00.500'"
    )
    with pytest.raises(ValueError, match="timezone"):
        arcgis.timestamp(datetime(2024, 5, 7))
    moment = datetime(2024, 5, 8, tzinfo=UTC)
    assert arcgis.epoch_ms(moment) == "1715126400000"
    assert arcgis.from_epoch_ms(1715126400000) == moment
    assert arcgis.from_epoch_ms(-3616790436000) == datetime(1855, 5, 22, 23, 59, 24, tzinfo=UTC)
    assert arcgis.from_epoch_ms(None) is None
    for bad in (True, 1.5, "0"):
        with pytest.raises(ValueError):
            arcgis.from_epoch_ms(bad)


def test_literals_double_their_quotes() -> None:
    assert arcgis.literal("O'Brien") == "'O''Brien'"


def test_ids_are_cut_into_sorted_runs_no_longer_than_a_page() -> None:
    assert arcgis.id_ranges([9, 3, 5, 3, 1, 12], 2) == [(1, 3), (5, 9), (12, 12)]
    assert arcgis.id_ranges([], 2000) == []
    assert arcgis.id_range("objectid", 5, 9) == "objectid >= 5 AND objectid <= 9"
    with pytest.raises(ValueError):
        arcgis.id_ranges([1], 0)


def test_a_query_url_carries_every_filter_in_a_fixed_order() -> None:
    url = httpx.URL(
        arcgis.query_url(
            LAYER,
            "stormdate IS NULL",
            bbox=BBox(west=-97.5, south=35.0, east=-96.0, north=36.5),
            order_by="objectid",
            moment=datetime(2024, 5, 8, tzinfo=UTC),
        )
    )
    assert url.path.endswith("/FeatureServer/0/query")
    assert list(url.params.items()) == [
        ("where", "stormdate IS NULL"),
        ("geometry", "-97.5,35,-96,36.5"),
        ("geometryType", "esriGeometryEnvelope"),
        ("inSR", "4326"),
        ("spatialRel", "esriSpatialRelIntersects"),
        ("outFields", "*"),
        ("outSR", "4326"),
        ("orderByFields", "objectid"),
        ("historicMoment", "1715126400000"),
        ("f", "geojson"),
    ]
    plain = httpx.URL(arcgis.query_url(LAYER + "/", "1=1"))
    assert list(plain.params) == ["where", "outFields", "outSR", "f"]


@pytest.mark.parametrize(
    "layer",
    [
        "http://example.test/FeatureServer/0",
        "https://example.test/FeatureServer/0?token=x",
        "https://example.test/FeatureServer/0#part",
        "https://example.test/FeatureServer",
        "https://example.test/FeatureServer/zero",
    ],
)
def test_a_layer_must_be_an_https_url_ending_in_its_number(layer: str) -> None:
    with pytest.raises(ValueError):
        arcgis.query_url(layer, "1=1")


def test_layer_metadata_is_read_with_its_archive() -> None:
    with respx.mock() as mock, http.client() as client:
        route = mock.get(LAYER, params={"f": "json"}).respond(200, json=INFO)
        info = arcgis.layer_info(LAYER, client)
    assert route.called
    assert info.max_record_count == 2000 and info.object_id_field == "objectid"
    assert info.fields == {"objectid", "stormdate"}
    assert info.formats == {"json", "geojson", "pbf"}
    assert info.has_attachments and info.query_attachments
    assert info.archive_start == datetime(2020, 11, 25, 17, 54, 29, tzinfo=UTC)
    unarchived = {k: v for k, v in INFO.items() if k != "archivingInfo"}
    with respx.mock() as mock, http.client() as client:
        mock.get(LAYER).respond(200, json=unarchived)
        assert arcgis.layer_info(LAYER, client).archive_start is None


@pytest.mark.parametrize(
    "body",
    [
        {**INFO, "maxRecordCount": 0},
        {**INFO, "maxRecordCount": True},
        {k: v for k, v in INFO.items() if k != "objectIdField"},
        {
            **INFO,
            "archivingInfo": {"supportsQueryWithHistoricMoment": True, "startArchivingMoment": "x"},
        },
    ],
)
def test_an_unusable_layer_description_is_refused(body: dict) -> None:
    with respx.mock() as mock, http.client() as client:
        mock.get(LAYER).respond(200, json=body)
        with pytest.raises(httpx.DecodingError):
            arcgis.layer_info(LAYER, client)


def test_an_error_body_is_refused_although_the_status_is_200() -> None:
    error = {"error": {"code": 400, "message": "Unable to complete operation.", "details": ["x"]}}
    with respx.mock() as mock, http.client() as client:
        mock.get(LAYER).respond(200, json=error)
        with pytest.raises(arcgis.ServiceError, match="400 Unable to complete operation"):
            arcgis.layer_info(LAYER, client)
        mock.get(f"{LAYER}/query").respond(200, text="<html>maintenance</html>")
        with pytest.raises(httpx.DecodingError, match="other than JSON"):
            arcgis.object_ids(LAYER, client, "1=1")


def test_object_ids_are_sorted_and_null_means_none() -> None:
    with respx.mock() as mock, http.client() as client:
        route = mock.get(f"{LAYER}/query").respond(200, json={"objectIds": [9, 3, 5]})
        assert arcgis.object_ids(
            LAYER, client, "1=1", bbox=BBox(west=-98, south=35, east=-97, north=36)
        ) == [3, 5, 9]
        params = route.calls[0].request.url.params
        assert params["returnIdsOnly"] == "true" and params["f"] == "json"
        assert "outFields" not in params and params["geometry"] == "-98,35,-97,36"
        mock.get(f"{LAYER}/query").respond(200, json={"objectIds": None})
        assert arcgis.object_ids(LAYER, client, "1=1") == []
        mock.get(f"{LAYER}/query").respond(200, json={"objectIds": ["3"]})
        with pytest.raises(httpx.DecodingError):
            arcgis.object_ids(LAYER, client, "1=1")


def test_a_features_page_the_service_cut_short_is_refused() -> None:
    features = [{"attributes": {"objectid": 1}}]
    with respx.mock() as mock, http.client() as client:
        mock.get(f"{LAYER}/query").respond(200, json={"features": features})
        assert arcgis.query_features(LAYER, client, "1=1", out_fields=["objectid"]) == features
        mock.get(f"{LAYER}/query").respond(
            200, json={"features": features, "exceededTransferLimit": True}
        )
        with pytest.raises(httpx.DecodingError, match="cut a page short"):
            arcgis.query_features(LAYER, client, "1=1", out_fields=["objectid"])


def attachment(parent: int, number: int, size: int = 10) -> dict:
    return {"parentObjectId": parent, "parentGlobalId": f"{{P{parent}}}", "attachmentInfos": [
        {"id": number, "globalId": f"{{A{number}}}", "name": f"{number}.jpg",
         "contentType": "image/jpeg", "size": size}
    ]}  # fmt: skip


def test_attachments_are_asked_for_in_batches_and_halved_at_the_silent_cap() -> None:
    asked: list[list[int]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        ids = [int(value) for value in request.url.params["objectIds"].split(",")]
        asked.append(ids)
        # Each feature holds one attachment; the service stops at three without saying so.
        return httpx.Response(
            200, json={"attachmentGroups": [attachment(i, i * 10) for i in ids[:3]]}
        )

    with respx.mock() as mock, http.client() as client:
        mock.get(f"{LAYER}/queryAttachments").mock(side_effect=respond)
        found = arcgis.query_attachments(LAYER, client, [1, 2, 3, 4, 5], max_records=3, batch=4)
    assert asked == [[1, 2, 3, 4], [1, 2], [3, 4], [5]]
    assert [(item.parent_id, item.id) for item in found] == [(i, i * 10) for i in range(1, 6)]
    assert found[0].url == f"{LAYER}/1/attachments/10"
    assert found[0].parent_global_id == "{P1}" and found[0].global_id == "{A10}"


def test_one_feature_at_the_cap_cannot_be_listed_completely() -> None:
    with respx.mock() as mock, http.client() as client:
        many = {"attachmentGroups": [attachment(1, 1), attachment(1, 2)]}
        mock.get(f"{LAYER}/queryAttachments").respond(200, json=many)
        with pytest.raises(httpx.DecodingError, match="feature 1 holds at least 2"):
            arcgis.query_attachments(LAYER, client, [1], max_records=2)


def test_attachment_queries_carry_the_moment() -> None:
    with respx.mock() as mock, http.client() as client:
        route = mock.get(f"{LAYER}/queryAttachments").respond(200, json={"attachmentGroups": []})
        moment = datetime(2024, 5, 8, tzinfo=UTC)
        assert arcgis.query_attachments(LAYER, client, [1], max_records=5, moment=moment) == []
    assert route.calls[0].request.url.params["historicMoment"] == "1715126400000"


def test_one_features_attachments_are_read_from_its_own_listing() -> None:
    infos = attachment(4, 40)["attachmentInfos"]
    with respx.mock() as mock, http.client() as client:
        mock.get(f"{LAYER}/4/attachments").respond(200, json={"attachmentInfos": infos})
        (found,) = arcgis.feature_attachments(LAYER, 4, client)
        assert (found.parent_id, found.id, found.size, found.name) == (4, 40, 10, "40.jpg")
        mock.get(f"{LAYER}/4/attachments").respond(200, json={"attachmentInfos": [{"id": "x"}]})
        with pytest.raises(httpx.DecodingError):
            arcgis.feature_attachments(LAYER, 4, client)


@pytest.mark.l2
def test_a_downloaded_page_must_be_a_whole_feature_collection(tmp_path: Path) -> None:
    page = tmp_path / "page.geojson"
    page.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
    arcgis.check_feature_collection(page)
    page.write_text(json.dumps({"error": {"code": 500, "message": "Error performing query"}}))
    with pytest.raises(arcgis.ServiceError, match="500 Error performing query"):
        arcgis.check_feature_collection(page)
    cut = {
        "type": "FeatureCollection",
        "features": [],
        "properties": {"exceededTransferLimit": True},
    }
    page.write_text(json.dumps(cut))
    with pytest.raises(httpx.DecodingError, match="cut short"):
        arcgis.check_feature_collection(page)
    for body in ('{"type": "Feature"}', "not json"):
        page.write_text(body)
        with pytest.raises(httpx.DecodingError):
            arcgis.check_feature_collection(page)
