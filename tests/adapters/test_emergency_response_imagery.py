"""NGS emergency response imagery: folder walking, footprint selection, refusals, and fetch."""

import struct
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx
import pytest
import respx

from usdata.models import TimeRange
from usdata.providers.base import QueryError
from usdata.providers.noaa.eri import (
    DEGREE_TOLERANCE,
    EmergencyResponseImagery,
)
from usdata.query import build_query
from usdata.registry import default_registry

HOST = "noaa-eri-pds.s3.amazonaws.com"
NS = 'xmlns="http://s3.amazonaws.com/doc/2006-03-01/"'
NASHVILLE = "2020_Nashville_Tornado"
FLIGHT = "20200307a_RGB"
# Four tiles on a 90-arc-second grid around 86°48'W 36°10'30"N, and one far to the east.
TILES = [
    "20200307aC0864800w361030n.tif",
    "20200307aC0864800w361200n.tif",
    "20200307aC0864930w361030n.tif",
    "20200307aC0864930w361200n.tif",
    "20200307aC0852700w360900n.tif",
]
TILE_SIZE = 50_000_000


def georeference_tags(
    *,
    west: float,
    north: float,
    pixel: float,
    size: int,
    keys: dict[int, int] | None,
) -> bytes:
    """A little-endian classic TIFF stating only where its first image lies."""
    entries: list[tuple[int, int, list[Any]]] = [
        (256, 4, [size]),
        (257, 4, [size]),
        (33550, 12, [pixel, pixel, 0.0]),
        (33922, 12, [0.0, 0.0, 0.0, west, north, 0.0]),
    ]
    if keys:
        directory = [1, 1, 0, len(keys)]
        for key, value in keys.items():
            directory += [key, 0, 1, value]
        entries.append((34735, 3, directory))
    codes = {3: "H", 4: "I", 12: "d"}
    offset = 8 + 2 + 12 * len(entries) + 4
    ifd, data = struct.pack("<H", len(entries)), b""
    for tag, kind, values in entries:
        payload = struct.pack("<" + codes[kind] * len(values), *values)
        field = payload.ljust(4, b"\0") if len(payload) <= 4 else struct.pack("<I", offset)
        if len(payload) > 4:
            data += payload
            offset += len(payload)
        ifd += struct.pack("<HHI", tag, kind, len(values)) + field
    return b"II" + struct.pack("<HI", 42, 8) + ifd + b"\0\0\0\0" + data


def degree_tile(west: float, north: float, span: float = 0.0252) -> bytes:
    """A geographic tile header: 252 pixels of span/252 degrees, buffered 0.0001° past its name."""
    return georeference_tags(
        west=west - 0.0001, north=north + 0.0001, pixel=span / 252, size=252, keys={1024: 2}
    )


class Bucket:
    """A public bucket answering delimited listings, byte ranges, and whole downloads."""

    def __init__(self, objects: dict[str, int], heads: dict[str, bytes] | None = None) -> None:
        self.objects = objects
        self.heads = heads or {}
        self.page = 1000
        self.listed: list[str] = []
        self.ranges: list[str] = []
        self.downloads: list[str] = []

    def respond(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return self.listing(request)
        key = unquote(request.url.path[1:])
        if "Range" in request.headers:
            self.ranges.append(key)
            start, end = (int(part) for part in request.headers["Range"][6:].split("-"))
            return httpx.Response(206, content=self.heads[key][start : end + 1])
        self.downloads.append(key)
        return httpx.Response(200, content=b"II*\x00 geotiff bytes of " + key.encode())

    def listing(self, request: httpx.Request) -> httpx.Response:
        params = request.url.params
        prefix = params["prefix"]
        assert params["delimiter"] == "/" and params["list-type"] == "2"
        self.listed.append(prefix)
        entries: dict[str, int | None] = {}
        for key, size in self.objects.items():
            if not key.startswith(prefix):
                continue
            head, slash, _ = key[len(prefix) :].partition("/")
            entries.setdefault(prefix + head + slash if slash else key, None if slash else size)
        ordered = sorted(entries.items())
        start = int(params.get("continuation-token", "0"))
        page = ordered[start : start + self.page]
        more = start + self.page < len(ordered)
        body = "".join(
            f"<CommonPrefixes><Prefix>{name}</Prefix></CommonPrefixes>"
            if size is None
            else f"<Contents><Key>{name}</Key><Size>{size}</Size></Contents>"
            for name, size in page
        )
        token = (
            f"<NextContinuationToken>{start + self.page}</NextContinuationToken>" if more else ""
        )
        return httpx.Response(
            200,
            text=f"<ListBucketResult {NS}><IsTruncated>{str(more).lower()}</IsTruncated>"
            f"{token}{body}</ListBucketResult>",
        )


def nashville() -> dict[str, int]:
    folder = f"{NASHVILLE}/{FLIGHT}/"
    return {
        **{folder + name: TILE_SIZE for name in TILES},
        folder + "20200307a_COG.vrt": 285_461,
        folder + "20200307a_tile_index.shp": 22_268,
        folder + "raw/131091_0307201505596_071_RGB1.jpg": 30_000_000,
        folder + "raw/0890900w290430n.tif": 524_000_000,
        f"{NASHVILLE}/downloads/20200307a_RGB.tar": 7_000_000_000,
        f"{NASHVILLE}/downloads/20200307a.sums": 105,
        "2011_Joplin_Tornado/may24JPEGtiles_UTMZone15/may24C350000e4102500n.tif": 1,
        "index.html": 32_357,
    }


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield EmergencyResponseImagery(
            default_registry().get("noaa:emergency-response-imagery"), client=client
        )


def serve(bucket: Bucket) -> respx.MockRouter:
    router = respx.mock(assert_all_called=False)
    router.route(host=HOST).mock(side_effect=bucket.respond)
    return router


def listed(adapter, bucket: Bucket, **kwargs):
    with serve(bucket):
        return adapter.list_assets(build_query(**kwargs))


def test_every_geotiff_of_an_event_without_raw_frames_or_download_archives(adapter) -> None:
    bucket = Bucket(nashville())
    assets = listed(adapter, bucket, event=NASHVILLE)
    keys = [f"{NASHVILLE}/{FLIGHT}/{name}" for name in TILES]
    assert [asset.id for asset in assets] == sorted(keys)
    first = assets[0]
    assert first.href == f"s3://noaa-eri-pds/{first.id}"
    assert first.dataset_id == "noaa:emergency-response-imagery"
    assert first.media_type == "image/tiff; application=geotiff"
    assert first.size == TILE_SIZE
    assert first.bbox is None and first.properties == {}
    # 7 March 2020, local: from midnight at UTC-4 to midnight at UTC-10.
    assert first.time == TimeRange(
        start=datetime(2020, 3, 7, 4, tzinfo=UTC), end=datetime(2020, 3, 8, 10, tzinfo=UTC)
    )
    # One listing per folder; the raw frames and the archives are never listed.
    assert bucket.listed == [f"{NASHVILLE}/", f"{NASHVILLE}/{FLIGHT}/"]
    assert bucket.ranges == []


def test_listing_follows_continuation_tokens(adapter) -> None:
    bucket = Bucket(nashville())
    bucket.page = 2
    assets = listed(adapter, bucket, event=NASHVILLE)
    assert len(assets) == len(TILES)
    # Five tiles, two index files, and the raw/ prefix: four pages of two.
    assert bucket.listed.count(f"{NASHVILLE}/{FLIGHT}/") == 4


def test_collections_select_folders_and_the_walk_goes_only_toward_them(adapter) -> None:
    event = "2022_Hurricane_Nicole"
    objects = {
        f"{event}/20221112a_RGB/20221112aC0804845w285445n.tif": 10,
        f"{event}/20221112a_RGB/ortho-cogs/061922_1112221943103_057_RGB1.tif": 20,
        f"{event}/20221112a_RGB/ortho-cogs/061922_1112221943103_057_RGB1.html": 1,
        f"{event}/20221113a_RGB/20221113aC0804845w285445n.tif": 30,
    }
    bucket = Bucket(objects)
    (asset,) = listed(adapter, bucket, event=event, collection="20221112a_RGB/ortho-cogs")
    assert asset.id.endswith("ortho-cogs/061922_1112221943103_057_RGB1.tif")
    assert f"{event}/20221113a_RGB/" not in bucket.listed
    both = listed(
        adapter, Bucket(objects), event=event, collection=["20221113a_RGB", "20221112a_RGB"]
    )
    assert [asset.size for asset in both] == [10, 30]


def test_an_unknown_event_names_the_near_spellings(adapter) -> None:
    bucket = Bucket(nashville())
    with pytest.raises(QueryError) as error:
        listed(adapter, bucket, event="2020_Nashvile_Tornado")
    message = str(error.value)
    assert "noaa-eri-pds has no event 2020_Nashvile_Tornado" in message
    assert "did you mean 2020_Nashville_Tornado" in message
    assert "its events are 2011_Joplin_Tornado, 2020_Nashville_Tornado" in message
    assert bucket.listed == ["2020_Nashvile_Tornado/", ""]


def test_an_unknown_collection_names_the_event_folders(adapter) -> None:
    with pytest.raises(
        QueryError, match=r"has no collection 20200307b_RGB; did you mean 20200307a_RGB\?"
    ):
        listed(adapter, Bucket(nashville()), event=NASHVILLE, collection="20200307b_RGB")


def test_an_event_with_nothing_but_raw_frames_holds_no_geotiff(adapter) -> None:
    objects = {f"{NASHVILLE}/{FLIGHT}/raw/0890900w290430n.tif": 5}
    with pytest.raises(QueryError, match="holds no GeoTIFF outside its raw/ and downloads/"):
        listed(adapter, Bucket(objects), event=NASHVILLE)


def test_a_bbox_keeps_the_tiles_whose_footprint_meets_it(adapter) -> None:
    sample = f"{NASHVILLE}/{FLIGHT}/{sorted(TILES)[0]}"
    bucket = Bucket(nashville(), {sample: degree_tile(-85.45, 36.15)})
    # Inside the tile whose north-west corner is 86°48'00"W 36°10'30"N, clear of its edges.
    (asset,) = listed(adapter, bucket, event=NASHVILLE, bbox=(-86.795, 36.155, -86.785, 36.17))
    assert asset.id.endswith("20200307aC0864800w361030n.tif")
    pad = DEGREE_TOLERANCE
    assert asset.bbox is not None
    assert asset.bbox.as_tuple() == pytest.approx(
        (-86.8 - pad, 36.175 - 0.0252 - pad, -86.8 + 0.0252 + pad, 36.175 + pad), abs=1e-12
    )
    # One header per folder, the first tile's, and only its first 64 KiB.
    assert bucket.ranges == [sample]
    # A box on the corner the four tiles share meets all four, not the far one.
    corner = listed(
        adapter,
        Bucket(nashville(), {sample: degree_tile(-85.45, 36.15)}),
        event=NASHVILLE,
        bbox=(-86.8, 36.175, -86.8, 36.175),
    )
    assert len(corner) == 4 and not any("0852700w" in asset.id for asset in corner)


def test_a_box_meeting_no_tile_selects_nothing(adapter) -> None:
    sample = f"{NASHVILLE}/{FLIGHT}/{sorted(TILES)[0]}"
    bucket = Bucket(nashville(), {sample: degree_tile(-85.45, 36.15)})
    assert listed(adapter, bucket, event=NASHVILLE, bbox=(-80.0, 30.0, -79.0, 31.0)) == []


def test_utm_tiles_are_placed_in_the_zone_their_folder_names(adapter) -> None:
    event, folder = "2011_Joplin_Tornado", "may24JPEGtiles_UTMZone15"
    names = ["may24C350000e4102500n.tif", "may24C372500e4100000n.tif"]
    objects = {f"{event}/{folder}/{name}": 1000 for name in names}
    header = georeference_tags(
        west=349950.125, north=4102549.875, pixel=0.25, size=10400, keys=None
    )
    bucket = Bucket(objects, {f"{event}/{folder}/{names[0]}": header})
    everything = listed(adapter, Bucket(objects), event=event)
    assert {asset.properties["utm_zone"] for asset in everything} == {"15"}
    # 372500 E 4100000 N in zone 15 is 94.4336°W 37.0376°N (pyproj, EPSG:26915).
    (asset,) = listed(adapter, bucket, event=event, bbox=(-94.43, 37.03, -94.42, 37.035))
    assert asset.id.endswith(names[1]) and asset.properties == {"utm_zone": "15"}
    assert asset.bbox is not None and asset.bbox.contains_point(37.0375, -94.4336)


def test_a_bbox_is_refused_where_file_names_give_no_footprint(adapter) -> None:
    event = "2016_Hurricane_Matthew"
    objects = {
        f"{event}/20161007aOblique/2016obP28168649.tif": 5,
        f"{event}/20161011_RGB_JpegTiles_GCS_NAD83/20161011aC0773730w355700n.tif": 5,
    }
    bucket = Bucket(objects)
    with pytest.raises(QueryError) as error:
        listed(adapter, bucket, event=event, bbox=(-78.0, 35.0, -77.0, 36.0))
    message = str(error.value)
    assert "cannot filter 2016_Hurricane_Matthew by location/bbox" in message
    assert "20161007aOblique (such as 2016obP28168649.tif) state no footprint" in message
    assert "with collection=, such as 20161011_RGB_JpegTiles_GCS_NAD83" in message
    assert bucket.ranges == []
    # Without a bbox the frames list like any other file.
    assert len(listed(adapter, Bucket(objects), event=event)) == 2


def test_utm_names_in_a_folder_naming_no_zone_refuse_a_bbox(adapter) -> None:
    event = "2009_NorEaster"
    objects = {f"{event}/nov15_images/nov15C377500e4087500n.tif": 5}
    with pytest.raises(QueryError, match=r"nov15_images .* state no footprint; list the event"):
        listed(adapter, Bucket(objects), event=event, bbox=(-77.0, 36.0, -76.0, 37.0))


def test_a_header_disagreeing_with_its_name_refuses_a_bbox(adapter) -> None:
    sample = f"{NASHVILLE}/{FLIGHT}/{sorted(TILES)[0]}"
    bucket = Bucket(nashville(), {sample: degree_tile(-85.0, 36.15)})
    with pytest.raises(QueryError, match="is not georeferenced where its name places it"):
        listed(adapter, bucket, event=NASHVILLE, bbox=(-86.795, 36.155, -86.785, 36.17))


def test_an_unreadable_header_refuses_a_bbox(adapter) -> None:
    sample = f"{NASHVILLE}/{FLIGHT}/{sorted(TILES)[0]}"
    bucket = Bucket(nashville(), {sample: b"<html>not a tiff</html>" + b"\0" * 20})
    with pytest.raises(QueryError, match=r"cannot read the georeferencing of .*not a TIFF"):
        listed(adapter, bucket, event=NASHVILLE, bbox=(-86.795, 36.155, -86.785, 36.17))


@pytest.mark.parametrize(
    ("header", "kept"),
    [
        # A geographic mosaic over the flight, 82.9°W to 82.4°W, 28.6°N to 29.1°N.
        (
            georeference_tags(west=-82.9, north=29.1, pixel=0.5 / 1000, size=1000, keys={1024: 2}),
            True,
        ),
        # The same area in Web Mercator metres.
        (
            georeference_tags(
                west=-9228487.0, north=3389401.0, pixel=55.66, size=1000, keys={1024: 1, 3072: 3857}
            ),
            True,
        ),
        # A mosaic far to the west of the box.
        (georeference_tags(west=-100.0, north=40.0, pixel=0.001, size=100, keys={1024: 2}), False),
    ],
)
def test_a_flight_mosaic_is_placed_by_its_own_header(adapter, header: bytes, kept: bool) -> None:
    event, folder = "2024_Hurricane_Debby", "20240807a_RGB"
    tile, mosaic = (
        f"{event}/{folder}/20240807aC0823300w285100n.tif",
        f"{event}/{folder}/{folder}.tif",
    )
    bucket = Bucket(
        {tile: 10, mosaic: 20}, {tile: degree_tile(-82.55, 28.85, 0.0127), mosaic: header}
    )
    assets = listed(adapter, bucket, event=event, bbox=(-82.545, 28.84, -82.54, 28.845))
    assert [asset.id for asset in assets] == ([tile, mosaic] if kept else [tile])
    assert sorted(bucket.ranges) == sorted([tile, mosaic])


def test_a_mosaic_in_an_unknown_projection_refuses_a_bbox(adapter) -> None:
    event, folder = "2024_Hurricane_Debby", "20240807a_RGB"
    mosaic = f"{event}/{folder}/{folder}.tif"
    header = georeference_tags(west=0.0, north=0.0, pixel=1.0, size=10, keys={1024: 1, 3072: 26915})
    with pytest.raises(QueryError, match="neither in degrees nor in Web Mercator"):
        listed(
            adapter, Bucket({mosaic: 20}, {mosaic: header}), event=event, bbox=(-83, 28, -82, 29)
        )


def test_a_selection_over_the_byte_budget_says_where_the_bytes_are(adapter) -> None:
    # Five 6 GB tiles; the raw frame and the other event's tile are not selected.
    big = {key: 6 * 10**9 for key in nashville() if key.endswith("n.tif")}
    with pytest.raises(QueryError) as error:
        listed(adapter, Bucket(big), event=NASHVILLE)
    assert str(error.value) == (
        f"{NASHVILLE} selects 5 files, 30.0 GB, more than max_gb=25; narrow it with a bbox or "
        f"collection, or raise max_gb. Largest collections: {FLIGHT} 5 files 30.0 GB"
    )
    assert len(listed(adapter, Bucket(big), event=NASHVILLE, max_gb="30")) == 5


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"event": "2020_Nashville_Tornado/"}, "event must be an event folder"),
        ({"event": "../2020_Nashville_Tornado"}, "event must be an event folder"),
        ({"event": "Nashville"}, "event must be an event folder"),
        ({}, "event is required"),
        ({"event": NASHVILLE, "collection": "/20200307a_RGB"}, "must name folders under the event"),
        ({"event": NASHVILLE, "collection": "a/../b"}, "must name folders under the event"),
        ({"event": NASHVILLE, "collection": ""}, "collection must not be empty"),
        ({"event": NASHVILLE, "collection": "20200307a_RGB/raw"}, "raw/ and downloads/"),
        ({"event": NASHVILLE, "collection": "downloads"}, "raw/ and downloads/"),
        ({"event": NASHVILLE, "max_gb": 0}, "max_gb must be a positive integer"),
        ({"event": NASHVILLE, "max_gb": "1.5"}, "max_gb must be a positive integer"),
    ],
)
def test_invalid_params_are_refused_before_any_request(adapter, params, message) -> None:
    bucket = Bucket(nashville())
    with serve(bucket), pytest.raises(QueryError, match=message):
        adapter.list_assets(build_query(**params))
    assert bucket.listed == [] and bucket.ranges == []


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        (
            {"start": "2020-03-07", "end": "2020-03-08"},
            "does not support start/end; flight folders",
        ),
        ({"variables": ["Red"]}, "does not support variables"),
    ],
)
def test_time_and_variables_are_refused(adapter, fields: dict[str, Any], message: str) -> None:
    bucket = Bucket(nashville())
    with serve(bucket), pytest.raises(QueryError, match=message):
        adapter.list_assets(build_query(event=NASHVILLE, **fields))
    assert bucket.listed == []


def test_fetch_downloads_the_whole_object(adapter, tmp_path: Path) -> None:
    bucket = Bucket(nashville())
    with serve(bucket):
        asset = adapter.list_assets(build_query(event=NASHVILLE))[0]
        path = adapter.fetch(asset, tmp_path / "tile.tif")
    assert path.read_bytes() == b"II*\x00 geotiff bytes of " + asset.id.encode()
    assert bucket.downloads == [asset.id]
