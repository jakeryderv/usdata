"""Where emergency response imagery tiles lie: names, GeoTIFF headers, and projections."""

import struct
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from usdata.models import BBox, TimeRange
from usdata.providers.noaa import eri, geotiff, utm
from usdata.providers.noaa.eri import Corner, corner, footprint, utm_zone

FIXTURES = Path(__file__).parents[1] / "fixtures" / "eri"
CODES = {3: "H", 4: "I", 12: "d"}


def tiff(
    *,
    order: str = "<",
    big: bool = False,
    width: int = 200,
    height: int = 100,
    scale: tuple[float, ...] = (0.5, 0.25, 0.0),
    tie: tuple[float, ...] = (0.0, 0.0, 0.0, 1000.0, 2000.0, 0.0),
    keys: dict[int, int] | None = None,
    data_at: int | None = None,
) -> bytes:
    """A TIFF holding only a first image file directory with georeferencing tags."""
    entries: list[tuple[int, int, list[float | int]]] = [
        (256, 4, [width]),
        (257, 4, [height]),
        (33550, 12, list(scale)),
        (33922, 12, list(tie)),
    ]
    if keys is not None:
        directory: list[float | int] = [1, 1, 0, len(keys)]
        for key, value in keys.items():
            directory += [key, 0, 1, value]
        entries.append((34735, 3, directory))
    count_format, entry_size, inline, pointer = ("Q", 20, 8, "Q") if big else ("H", 12, 4, "I")
    start = 16 if big else 8
    length = struct.calcsize(count_format) + entry_size * len(entries) + struct.calcsize(pointer)
    data_offset = data_at if data_at is not None else start + length
    directory_bytes, data = struct.pack(order + count_format, len(entries)), b""
    for tag, kind, values in entries:
        payload = struct.pack(order + CODES[kind] * len(values), *values)
        if len(payload) <= inline:
            field = payload.ljust(inline, b"\0")
        else:
            field = struct.pack(order + pointer, data_offset + len(data))
            data += payload
        number = struct.pack(order + pointer, len(values))
        directory_bytes += struct.pack(order + "HH", tag, kind) + number + field
    directory_bytes += b"\0" * struct.calcsize(pointer)
    magic = b"II" if order == "<" else b"MM"
    if big:
        header = magic + struct.pack(order + "HHHQ", 43, 8, 0, start)
    else:
        header = magic + struct.pack(order + "HI", 42, start)
    return (header + directory_bytes).ljust(data_offset, b"\0") + data


def whole(body: bytes) -> geotiff.Read:
    return lambda offset, length: body[offset : offset + length]


@pytest.mark.parametrize(("order", "big"), [("<", False), (">", False), ("<", True), (">", True)])
def test_classic_and_bigtiff_in_either_byte_order(order: str, big: bool) -> None:
    body = tiff(order=order, big=big, keys={1024: 1, 3072: 3857})
    reference = geotiff.parse(body, whole(body))
    assert reference == geotiff.Georeference(
        width=200,
        height=100,
        west=1000.0,
        north=2000.0,
        pixel_width=0.5,
        pixel_height=0.25,
        model_type=1,
        projected_crs=3857,
    )
    assert reference.span == (100.0, 25.0)
    assert reference.extent == (1000.0, 1975.0, 1100.0, 2000.0)


def test_values_past_the_first_bytes_are_read_by_range() -> None:
    body = tiff(data_at=100_000)
    reads: list[tuple[int, int]] = []

    def read(offset: int, length: int) -> bytes:
        reads.append((offset, length))
        return body[offset : offset + length]

    reference = geotiff.parse(body[:1024], read)
    assert reference.west == 1000.0 and reference.pixel_height == 0.25
    assert reads == [(100_000, 24), (100_024, 48)]


def test_a_point_registered_raster_starts_half_a_pixel_out() -> None:
    point = tiff(keys={1024: 2, 1025: 2})
    area = tiff(keys={1024: 2, 1025: 1})
    assert geotiff.parse(point, whole(point)).extent == (999.75, 1975.125, 1099.75, 2000.125)
    assert geotiff.parse(area, whole(area)).extent == (1000.0, 1975.0, 1100.0, 2000.0)


def test_a_tiepoint_away_from_the_first_pixel_is_carried_back_to_it() -> None:
    body = tiff(tie=(10.0, 4.0, 0.0, 1000.0, 2000.0, 0.0))
    reference = geotiff.parse(body, whole(body))
    assert (reference.west, reference.north) == (995.0, 2001.0)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"GIF89a" + b"\0" * 20, "not a TIFF"),
        (b"II\x2b\x00" + b"\0" * 20, "not a TIFF"),
        (b"II\x2c\x00" + b"\0" * 20, "not a TIFF"),
        (b"II\x2a\x00" + b"\0" * 20, "no image file directory"),
        (b"II\x2a\x00\x08\x00\x00\x00\xff\xff" + b"\0" * 20, "65535 entries"),
        # A pixel scale claiming 2**20 doubles.
        (
            tiff().replace(
                struct.pack("<HHI", 33550, 12, 3), struct.pack("<HHI", 33550, 12, 1 << 20)
            ),
            "claims",
        ),
        (tiff(scale=(0.0, 0.25, 0.0)), "malformed"),
        (tiff(tie=(0.0, 0.0, 0.0)), "malformed"),
    ],
)
def test_malformed_files_are_refused(body: bytes, message: str) -> None:
    with pytest.raises(geotiff.GeoTiffError, match=message):
        geotiff.parse(body, whole(body))


def test_a_missing_tag_or_a_short_file_is_refused() -> None:
    body = tiff()
    without_scale = body.replace(struct.pack("<HH", 33550, 12), struct.pack("<HH", 999, 12))
    with pytest.raises(geotiff.GeoTiffError, match="ModelPixelScale"):
        geotiff.parse(without_scale, whole(without_scale))
    far = tiff(data_at=100_000)
    with pytest.raises(geotiff.GeoTiffError, match="ends before"):
        geotiff.parse(far[:1024], lambda offset, length: b"")


@pytest.mark.l2
def test_real_headers_place_their_images() -> None:
    joplin = geotiff.parse((FIXTURES / "joplin-utm-tile.head").read_bytes(), whole(b""))
    assert joplin.model_type is None and joplin.projected_crs is None
    assert (joplin.west, joplin.north) == (372474.375, 4100049.875)
    assert joplin.span == (2600.0, 2600.0)
    helene = geotiff.parse((FIXTURES / "helene-point-tile.head").read_bytes(), whole(b""))
    assert helene.model_type == 2 and (helene.width, helene.height) == (14122, 14122)
    assert helene.west == pytest.approx(-85.4001, abs=1e-9)
    assert helene.north == pytest.approx(29.7126, abs=1e-9)
    assert helene.span[0] == pytest.approx(0.0127, abs=1e-9)
    debby = geotiff.parse((FIXTURES / "debby-mosaic-bigtiff.head").read_bytes(), whole(b""))
    assert (debby.model_type, debby.projected_crs) == (1, 3857)
    assert (debby.width, debby.height) == (35328, 36352)
    # EPSG:3857 to EPSG:4326 by pyproj 3.8.0: (-83.2928466796875, 28.796546241769207) and
    # (-82.5347900390625, 29.477861195816843).
    box = eri._mosaic_footprint(debby)
    assert box is not None
    assert box.as_tuple() == pytest.approx(
        (-83.2928466796875, 28.796546241769207, -82.5347900390625, 29.477861195816843), abs=1e-9
    )


def test_a_mosaic_in_another_projection_is_not_placed() -> None:
    projected = geotiff.parse(tiff(keys={1024: 1, 3072: 26915}), whole(b""))
    unknown = geotiff.parse(tiff(), whole(b""))
    geographic = geotiff.parse(
        tiff(scale=(0.01, 0.01, 0.0), tie=(0, 0, 0, -83.0, 29.0, 0), keys={1024: 2}), whole(b"")
    )
    assert eri._mosaic_footprint(projected) is None
    assert eri._mosaic_footprint(unknown) is None
    assert eri._mosaic_footprint(geographic) == BBox(west=-83.0, south=28.0, east=-81.0, north=29.0)


def dms(degrees: int, minutes: int, seconds: int) -> float:
    return degrees + minutes / 60 + seconds / 3600


@pytest.mark.parametrize(
    ("folder", "name", "expected"),
    [
        ("20200307a_RGB", "20200307aC0852700w360900n.tif", (-85.45, 36.15)),
        ("aug30JpegTiles_GCS_NAD83", "aug30C0882700w301930n.tif", (-88.45, 30.325)),
        ("nov06bJpegTiles_GCS_NAD83", "nov06b0740600w394930n.tif", (-74.1, dms(39, 49, 30))),
        ("20161013_RGB_JpegTiles_GCS_NAD83", "0771630w353730n.tif", (-dms(77, 16, 30), 35.625)),
        (
            "CB2201a_OB_N_RGB",
            "CB2201a_OB_NC0644930w174545n.tif",
            (-dms(64, 49, 30), dms(17, 45, 45)),
        ),
        ("20170915_16_USVI", "20170915_16_USVI_C0644030w181930n.tif", (-dms(64, 40, 30), 18.325)),
        # A truncated second: 30'44" stands for 30'45"; the footprint tolerance covers it.
        ("20240927a_RGB", "20240927aC0853044w295830n.tif", (-dms(85, 30, 44), 29.975)),
        ("east", "0100000e100000s.tif", (10.0, -10.0)),
    ],
)
def test_degree_names_state_the_north_west_corner(
    folder: str, name: str, expected: tuple[float, float]
) -> None:
    found = corner(folder, name)
    assert found is not None and found.zone is None
    assert (found.x, found.y) == pytest.approx(expected, abs=1e-12)


def test_utm_names_are_read_only_in_a_folder_naming_its_zone() -> None:
    assert corner("may24JPEGtiles_UTMZone15", "may24C350000e4102500n.tif") == Corner(
        350000.0, 4102500.0, 15
    )
    assert corner("nov15_images", "nov15C377500e4087500n.tif") is None
    assert corner("Final_C1_images", "C377500e4087500n.tif") is None


@pytest.mark.parametrize(
    "name",
    [
        "29907494.tif",
        "geo-24566091.tif",
        "geo-C24700126.tif",
        "S18367842.tif",
        "2016obP28168649.tif",
        "20200918bRR26261021.tif",
        "061922_1112221943103_057_RGB1.tif",
        "mwflood-28-98.tif",
        "20240807a_RGB.tif",
        "20200307aC0856000w360900n.tif",
        "20200307aC0852700w366000n.tif",
        "20200307aC1852700w360900n.tif",
        "20200307aC0852700w950000n.tif",
        "20200307aC0852700w360900n.vrt",
        "120200307aC0852700w360900n.tif.jpg",
    ],
)
def test_names_that_state_no_corner(name: str) -> None:
    assert corner("20200307a_RGB", name) is None


@pytest.mark.parametrize(
    ("folder", "zone"),
    [
        ("may24JPEGtiles_UTMZone15", 15),
        ("event/aug28JPEGtiles_UTMZone18", 18),
        ("UTMZone61", None),
        ("UTMZone0", None),
        ("UTMZone15/sub", None),
        ("nov15_images", None),
    ],
)
def test_utm_zone_comes_from_the_folder_name(folder: str, zone: int | None) -> None:
    assert utm_zone(folder) == zone


def contains(box: BBox, west: float, south: float, east: float, north: float) -> bool:
    return box.west <= west and box.south <= south and box.east >= east and box.north >= north


def test_a_degree_footprint_holds_the_tile_its_header_places() -> None:
    # The Nashville tile's header: -85.4501 to -85.4249, 36.1249 to 36.1501.
    box = footprint(Corner(-85.45, 36.15), (0.0252, 0.0252))
    assert contains(box, -85.4501, 36.1249, -85.4249, 36.1501)
    assert box.as_tuple() == pytest.approx(
        (-85.45 - 2 / 3600, 36.1248 - 2 / 3600, -85.4248 + 2 / 3600, 36.15 + 2 / 3600)
    )
    # A truncated name: the Helene tile's header runs -85.5126 to -85.4999, 29.9624 to 29.9751.
    truncated = footprint(Corner(-dms(85, 30, 44), 29.975), (0.0127, 0.0127))
    assert contains(truncated, -85.5126, 29.9624, -85.4999, 29.9751)


@pytest.mark.l2
def test_a_utm_footprint_holds_the_tile_its_header_places() -> None:
    header = geotiff.parse((FIXTURES / "joplin-utm-tile.head").read_bytes(), whole(b""))
    box = footprint(Corner(372500.0, 4100000.0, 15), header.span)
    west, south, east, north = header.extent
    for x in (west, east):
        for y in (south, north):
            lon, lat = utm.to_lonlat(15, x, y)
            assert box.contains_point(lat, lon)
    assert box.east - box.west < 0.035 and box.north - box.south < 0.03


def test_footprints_stay_on_the_globe() -> None:
    box = footprint(Corner(-180.0, 90.0), (0.0252, 0.0252))
    assert box.west == -180 and box.north == 90


@pytest.mark.parametrize(
    ("zone", "easting", "northing", "lon", "lat"),
    [
        # Reference values from pyproj 3.8.0, EPSG:269xx to EPSG:4269.
        (15, 350000, 4102500, -94.687034112, 37.056760536),
        (15, 372500, 4100000, -94.4336336678723, 37.037560371021),
        (18, 305000, 3837500, -77.128031083, 34.660906716),
        (18, 166000, 5000000, -79.243271169, 45.074578463),
        (18, 833000, 1000000, -71.971425082, 9.034053998),
        (10, 500000, 0, -123.0, 0.0),
        (1, 500000, 9000000, -177.0, 81.060880976),
    ],
)
def test_utm_to_longitude_and_latitude(
    zone: int, easting: float, northing: float, lon: float, lat: float
) -> None:
    assert utm.to_lonlat(zone, easting, northing) == pytest.approx((lon, lat), abs=1e-8)


def local_day(first: datetime, last: datetime | None = None) -> TimeRange:
    """A local calendar day or run of days, as UTC in U.S. zones from UTC-4 to UTC-10."""
    return TimeRange(
        start=first + timedelta(hours=4), end=(last or first) + timedelta(days=1, hours=10)
    )


@pytest.mark.parametrize(
    ("event", "folder", "expected"),
    [
        ("2020_Nashville_Tornado", "20200307a_RGB", local_day(datetime(2020, 3, 7, tzinfo=UTC))),
        (
            "2015_Midwest_Flood",
            "20160103aRGB_NADIR_JpegTiles_GCS_NAD83",
            local_day(datetime(2016, 1, 3, tzinfo=UTC)),
        ),
        (
            "2022_Hurricane_Nicole",
            "20221112a_RGB/ortho-cogs",
            local_day(datetime(2022, 11, 12, tzinfo=UTC)),
        ),
        (
            "2017_Hurricane_Irma",
            "20170915_16_USVI",
            local_day(datetime(2017, 9, 15, tzinfo=UTC), datetime(2017, 9, 16, tzinfo=UTC)),
        ),
        (
            "2011_Joplin_Tornado",
            "may24JPEGtiles_UTMZone15",
            local_day(datetime(2011, 5, 24, tzinfo=UTC)),
        ),
        ("2009_NorEaster", "nov15_images", local_day(datetime(2009, 11, 15, tzinfo=UTC))),
        (
            "2005_Hurricane_Wilma",
            "WILMA_29907494_1",
            TimeRange(start=datetime(2005, 1, 1, tzinfo=UTC)),
        ),
        ("2009_NorEaster", "Final_C1_images", TimeRange(start=datetime(2009, 1, 1, tzinfo=UTC))),
        ("2023_Pre_Event", "EC2301a_OB_N_RGB", TimeRange(start=datetime(2023, 1, 1, tzinfo=UTC))),
        (
            "2020_Nashville_Tornado",
            "20201399a_RGB",
            TimeRange(start=datetime(2020, 1, 1, tzinfo=UTC)),
        ),
        ("2011_Joplin_Tornado", "feb30_images", TimeRange(start=datetime(2011, 1, 1, tzinfo=UTC))),
    ],
)
def test_flight_time_is_the_local_day_a_folder_names(
    event: str, folder: str, expected: TimeRange
) -> None:
    assert eri.flight_time(event, folder) == expected


@pytest.mark.parametrize("zone", [0, 61])
def test_utm_zone_must_exist(zone: int) -> None:
    with pytest.raises(ValueError, match="1 to 60"):
        utm.to_lonlat(zone, 500000, 0)
