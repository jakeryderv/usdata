import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from usdata import ChecksumMismatch
from usdata.protocols import s3
from usdata.providers.base import QueryError
from usdata.providers.noaa.goes import GoesAbi
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

PREFIX = "ABI-L2-CMIPC/2024/127/12/"
NAME = "OR_ABI-L2-CMIPC-M6C06_G18_s20241271201181_e20241271203560_c20241271204021.nc"
KEY = PREFIX + NAME
LIST_URL = "https://noaa-goes18.s3.amazonaws.com/"
DATA = b"\x89HDF\r\n\x1a\nmock scene bytes"


def listing(keys, token=None):
    items = "".join(f"<Contents><Key>{k}</Key><Size>{s}</Size></Contents>" for k, s in keys)
    trunc = (
        f"<IsTruncated>true</IsTruncated><NextContinuationToken>{token}</NextContinuationToken>"
        if token
        else "<IsTruncated>false</IsTruncated>"
    )
    return f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">{trunc}{items}</ListBucketResult>'


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield GoesAbi(default_registry().get("noaa:goes-abi"), client=client)


def query(**kwargs):
    args: dict[str, Any] = {
        "start": "2024-05-06T12:00Z",
        "end": "2024-05-06T12:05Z",
        "satellite": 18,
        "channel": 6,
    }
    args.update(kwargs)
    return build_query(**args)


def test_listing_paginates_filters_and_preserves_scene_metadata(adapter):
    invalid = [
        KEY.replace("C06", "C13"),
        KEY.replace("G18", "G16"),
        KEY.replace("CMIPC", "CMIPF"),
        KEY + ".json",
        PREFIX + "folder/" + NAME,
        KEY.replace("s20241271201181", "s20249991201181"),
        KEY.replace("e20241271203560", "e20241271200180"),
        KEY.replace("2024/127/12", "2024/127/11"),
        KEY.replace("s20241271201181", "s20241271206181"),
    ]
    with respx.mock() as mock:
        route = mock.get(LIST_URL)
        route.side_effect = [
            httpx.Response(
                200, text=listing([(KEY, 255384), *[(key, 10) for key in invalid]], "next")
            ),
            httpx.Response(200, text=listing([(KEY, 255384)])),
        ]
        (asset,) = adapter.list_assets(query(channel="C06", satellite="18"))
    assert route.call_count == 2
    assert route.calls[0].request.url.params["prefix"] == PREFIX
    assert route.calls[1].request.url.params["continuation-token"] == "next"
    assert asset.id == NAME and asset.href == f"s3://noaa-goes18/{KEY}"
    assert asset.size == 255384 and asset.media_type == "application/x-netcdf"
    assert asset.bbox is None and asset.checksum is None
    assert asset.time.start == datetime(2024, 5, 6, 12, 1, 18, 100000, tzinfo=UTC)
    assert asset.time.end == datetime(2024, 5, 6, 12, 3, 56, tzinfo=UTC)


@pytest.mark.parametrize(
    ("start", "end", "count"),
    [
        ("2024-05-06T12:01:18.1Z", "2024-05-06T12:01:18.1Z", 1),
        ("2024-05-06T14:01:18.1+02:00", "2024-05-06T14:01:18.1+02:00", 1),
        ("2024-05-06T12:01:18.100001Z", "2024-05-06T12:03:00Z", 0),
        ("2024-05-06T12:00:00Z", "2024-05-06T12:01:18.099999Z", 0),
    ],
)
def test_scan_start_selection_is_inclusive_not_overlap(adapter, start, end, count):
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([(KEY, 100)]))
        assert len(adapter.list_assets(query(start=start, end=end))) == count


def test_hours_cross_year_and_all_scan_modes(adapter):
    first = "ABI-L2-CMIPC/2023/365/23/" + NAME.replace("M6", "M3").replace(
        "20241271201181", "20233652359181"
    ).replace("20241271203560", "20240010001560")
    second = "ABI-L2-CMIPC/2024/001/00/" + NAME.replace("M6", "M4").replace(
        "20241271201181", "20240010001181"
    ).replace("20241271203560", "20240010003560")
    with respx.mock() as mock:
        route = mock.get(LIST_URL)
        route.side_effect = [
            httpx.Response(200, text=listing([(first, 10)])),
            httpx.Response(200, text=listing([(second, 11)])),
        ]
        assets = adapter.list_assets(query(start="2023-12-31T23:59Z", end="2024-01-01T00:02Z"))
    assert len(assets) == 2
    assert [call.request.url.params["prefix"] for call in route.calls] == [
        "ABI-L2-CMIPC/2023/365/23/",
        "ABI-L2-CMIPC/2024/001/00/",
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"start": None},
        {"end": None},
        {"channel": None},
        {"satellite": None},
        {"satellite": 15},
        {"satellite": 20},
        {"satellite": True},
        {"satellite": []},
        {"channel": True},
        {"channel": 1.0},
        {"channel": ""},
        {"channel": "C17"},
        {"channel": 0},
        {"channel": "foo"},
        {"channel": [6]},
        {"channel": "\uff11"},
        {"product": "ABI-L2-CMIPF", "channel": None},
        {"product": "ABI-L2-CMIPM"},
        {"product": "ABI-L2-CMIPM", "sector": None},
        {"product": "ABI-L2-CMIPM", "sector": "M3"},
        {"product": "ABI-L2-CMIPM", "sector": "C"},
        {"product": "ABI-L2-CMIPM", "sector": ""},
        {"product": "ABI-L2-CMIPM", "sector": ["M1", "M2"]},
        {"product": "ABI-L2-CMIPM", "sector": True},
        {"sector": "M1"},
        {"product": "ABI-L2-CMIPF", "sector": "M1"},
        # Products select directories exactly: no aliases, other cases, or unsupported ones.
        {"product": "MCMIPC"},
        {"product": "abi-l2-mcmipc", "channel": None},
        {"product": "ABI-L2-MCMIP", "channel": None},
        {"product": "ABI-L2-ACHA2KMC", "channel": None},
        {"product": "ABI-L2-ACHTC", "channel": None},
        {"product": "ABI-L2-CTPM", "channel": None, "sector": "M1"},
        {"product": "ABI-L2-ACMC", "channel": None},
        {"product": "ABI-L2-RadC"},
        {"product": ""},
        {"product": ["ABI-L2-CMIPC", "ABI-L2-MCMIPC"]},
        # Only the single-channel products take a channel.
        {"product": "ABI-L2-MCMIPC"},
        {"product": "ABI-L2-MCMIPF", "channel": "C13"},
        {"product": "ABI-L2-MCMIPM", "sector": "M1"},
        {"product": "ABI-L2-ACHAC"},
        {"product": "ABI-L2-CTPF", "channel": 13},
        # Only the mesoscale products take a sector, and every one of them needs it.
        {"product": "ABI-L2-MCMIPC", "channel": None, "sector": "M1"},
        {"product": "ABI-L2-ACHAF", "channel": None, "sector": "M2"},
        {"product": "ABI-L2-MCMIPM", "channel": None},
        {"product": "ABI-L2-ACHTM", "channel": None, "sector": "C"},
        {"product": "ABI-L2-ACTPM", "channel": None, "sector": None},
        # Each product's archive starts on its own first day.
        {
            "product": "ABI-L2-ACHAC",
            "channel": None,
            "start": "2019-12-01T00:00",
            "end": "2019-12-01T23:59",
        },
        {
            "product": "ABI-L2-CTPC",
            "channel": None,
            "start": "2019-12-02T00:00",
            "end": "2019-12-04T23:59",
        },
        {"channels": "6,13"},
        {"location": "ok"},
        {"variables": ["CMI"]},
        {"text": "clouds"},
        {"start": "2000-01-01T12:00", "end": "2000-01-01T12:05"},
        {"start": "2024-05-01T00:00", "end": "2024-05-08T00:01"},
    ],
)
def test_bad_queries_fail_before_network(adapter, params):
    with respx.mock() as mock, pytest.raises(QueryError):
        adapter.list_assets(query(**params))
    assert not mock.calls


def test_reject_non_leap_day_366(adapter):
    key = KEY.replace("2024/127", "2023/365").replace("2024127", "2023366")
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([(key, 100)]))
        assert adapter.list_assets(query(start="2023-12-31T12:00", end="2023-12-31T12:05")) == []


@pytest.mark.parametrize("sector", ["M1", "M2"])
def test_mesoscale_shared_prefix_filters_sector_across_pages(adapter, sector):
    prefix = "ABI-L2-CMIPM/2024/127/22/"
    name = f"OR_ABI-L2-CMIP{sector}-M6C13_G16_s20241272200280_e20241272200349_c20241272200404.nc"
    key = prefix + name
    other = "M2" if sector == "M1" else "M1"
    invalid = [
        key.replace(f"CMIP{sector}-", f"CMIP{other}-"),
        key.replace(f"CMIP{sector}-", "CMIPC-"),
        key.replace("C13_G16", "C06_G16"),
        key.replace("G16", "G18"),
        key.replace("CMIPM/", "CMIPC/"),
        key.replace("s20241272200280", "s20241272200279"),
        key.replace("s20241272200280", "s20241272200281"),
    ]
    with respx.mock() as mock:
        route = mock.get("https://noaa-goes16.s3.amazonaws.com/")
        route.side_effect = [
            httpx.Response(200, text=listing([(k, 10) for k in invalid], "page2")),
            httpx.Response(200, text=listing([(key, 329131), (key, 329131)])),
        ]
        (asset,) = adapter.list_assets(
            query(
                satellite=16,
                channel=13,
                product="ABI-L2-CMIPM",
                sector=sector,
                start="2024-05-06T22:00:28Z",
                end="2024-05-06T22:00:28Z",
            )
        )
    assert [call.request.url.params["prefix"] for call in route.calls] == [prefix, prefix]
    assert route.calls[1].request.url.params["continuation-token"] == "page2"
    assert asset.id == name and asset.href == f"s3://noaa-goes16/{key}"
    assert asset.size == 329131
    assert asset.time.start == datetime(2024, 5, 6, 22, 0, 28, tzinfo=UTC)
    assert asset.time.end == datetime(2024, 5, 6, 22, 0, 34, 900000, tzinfo=UTC)


def test_explicit_null_sector_preserves_conus_default(adapter):
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([(KEY, 100)]))
        assert len(adapter.list_assets(query(sector=None))) == 1


# Real GOES-16 filenames listed on 2026-09-29 under each product's 2024/127/22/ prefix.
PRODUCT_FILES = {
    "ABI-L2-CMIPF": "OR_ABI-L2-CMIPF-M6C01_G16_s20241272200205_e20241272209513_c20241272209574.nc",
    "ABI-L2-MCMIPC": "OR_ABI-L2-MCMIPC-M6_G16_s20241272201173_e20241272203551_c20241272204067.nc",
    "ABI-L2-MCMIPF": "OR_ABI-L2-MCMIPF-M6_G16_s20241272200205_e20241272209513_c20241272209597.nc",
    "ABI-L2-MCMIPM": "OR_ABI-L2-MCMIPM1-M6_G16_s20241272200280_e20241272200350_c20241272200421.nc",
    "ABI-L2-ACHAC": "OR_ABI-L2-ACHAC-M6_G16_s20241272201173_e20241272203546_c20241272206330.nc",
    "ABI-L2-ACHAF": "OR_ABI-L2-ACHAF-M6_G16_s20241272200205_e20241272209513_c20241272213064.nc",
    "ABI-L2-ACHAM": "OR_ABI-L2-ACHAM1-M6_G16_s20241272200280_e20241272200338_c20241272201218.nc",
    "ABI-L2-ACHTF": "OR_ABI-L2-ACHTF-M6_G16_s20241272200205_e20241272209513_c20241272213066.nc",
    "ABI-L2-ACHTM": "OR_ABI-L2-ACHTM1-M6_G16_s20241272200280_e20241272200338_c20241272201219.nc",
    "ABI-L2-CTPC": "OR_ABI-L2-CTPC-M6_G16_s20241272201173_e20241272203546_c20241272206329.nc",
    "ABI-L2-CTPF": "OR_ABI-L2-CTPF-M6_G16_s20241272200205_e20241272209513_c20241272213063.nc",
    "ABI-L2-ACTPC": "OR_ABI-L2-ACTPC-M6_G16_s20241272201173_e20241272203546_c20241272205202.nc",
    "ABI-L2-ACTPF": "OR_ABI-L2-ACTPF-M6_G16_s20241272200205_e20241272209513_c20241272211163.nc",
    "ABI-L2-ACTPM": "OR_ABI-L2-ACTPM1-M6_G16_s20241272200280_e20241272200338_c20241272201009.nc",
}


def neighbours(name: str, product: str) -> list[str]:
    """Filenames that share the directory's shape but belong to another selection."""
    family, scene = product[:-1].removeprefix("ABI-L2-"), product[-1]
    code = f"{scene}1" if scene == "M" else scene
    tag = f"{family}{code}-"
    others = [
        name.replace("_G16_", "_G18_"),
        name.replace(tag, f"{family}2KM{code}-"),
        name.replace(tag, f"{family}{'M2' if scene == 'M' else 'F' if scene == 'C' else 'C'}-"),
        name.replace(f"-{family}", "-CMIP" if family == "MCMIP" else f"-M{family}"),
    ]
    if family == "CMIP":
        others.append(name.replace("-M6C01_", "-M6C02_"))
        others.append(name.replace("-M6C01_", "-M6_"))
    else:
        others.append(name.replace("-M6_", "-M6C13_"))
    assert len(set(others)) == len(others) and name not in others
    return others


@pytest.mark.parametrize("product", sorted(PRODUCT_FILES))
def test_every_product_lists_its_own_directory_and_filenames(adapter, product):
    name = PRODUCT_FILES[product]
    prefix = f"{product}/2024/127/22/"
    key = prefix + name
    params: dict[str, Any] = {"product": product, "channel": 1 if "-CMIP" in product else None}
    if product.endswith("M"):
        params["sector"] = "M1"
    with respx.mock() as mock:
        route = mock.get("https://noaa-goes16.s3.amazonaws.com/")
        route.side_effect = [
            httpx.Response(
                200, text=listing([(prefix + n, 10) for n in neighbours(name, product)], "p2")
            ),
            httpx.Response(200, text=listing([(key, 4505610)])),
        ]
        (asset,) = adapter.list_assets(
            query(satellite=16, start="2024-05-06T22:00Z", end="2024-05-06T22:05Z", **params)
        )
    assert [call.request.url.params["prefix"] for call in route.calls] == [prefix, prefix]
    assert asset.id == name and asset.href == f"s3://noaa-goes16/{key}"
    assert asset.size == 4505610 and asset.properties == {}
    stamp = name.split("_s")[1][:14]
    assert f"{asset.time.start:%Y%j%H%M%S}{asset.time.start.microsecond // 100000}" == stamp


@pytest.mark.parametrize(
    ("params", "message"),
    [
        (
            {"product": "ABI-L2-MCMIPC"},
            "channel is only supported with ABI-L2-CMIPC, CMIPF, or CMIPM, not ABI-L2-MCMIPC "
            "(its file holds all 16 bands)",
        ),
        ({"product": "ABI-L2-ACHAC"}, "channel is only supported with"),
        (
            {"product": "ABI-L2-CMIPF", "channel": None},
            "channel (1 to 16 or C01 to C16) is required",
        ),
        (
            {"product": "ABI-L2-ACHTM", "channel": None},
            "sector=M1 or M2 is required for mesoscale product=ABI-L2-ACHTM",
        ),
        (
            {"product": "ABI-L2-CTPF", "channel": None, "sector": "M1"},
            "sector is only supported with mesoscale products, not ABI-L2-CTPF",
        ),
        ({"product": "ABI-L2-CTPM", "channel": None}, "product must be ABI-L2-CMIPC, "),
        (
            {
                "product": "ABI-L2-ACHAF",
                "channel": None,
                "start": "2019-11-30",
                "end": "2019-12-01",
            },
            "ABI-L2-ACHAF files begin on 2019-12-02",
        ),
    ],
)
def test_selector_mistakes_are_named(adapter, params, message):
    with respx.mock() as mock, pytest.raises(QueryError, match=re.escape(message)):
        adapter.list_assets(query(**params))
    assert not mock.calls


def test_window_before_product_start_is_clamped_to_its_first_day(adapter):
    with respx.mock() as mock:
        route = mock.get("https://noaa-goes16.s3.amazonaws.com/")
        route.respond(200, text=listing([]))
        adapter.list_assets(
            query(
                satellite=16,
                product="ABI-L2-CTPC",
                channel=None,
                start="2019-12-04T23:00Z",
                end="2019-12-05T00:30Z",
            )
        )
    assert [call.request.url.params["prefix"] for call in route.calls] == [
        "ABI-L2-CTPC/2019/339/00/"
    ]


@pytest.mark.l2
@pytest.mark.parametrize("sector", [None, "M1", "M2"])
def test_manifest_restore_does_not_relist_and_checks_bytes(tmp_path: Path, sector):
    key = (
        KEY
        if sector is None
        else KEY.replace("CMIPC/", "CMIPM/").replace("CMIPC-", f"CMIP{sector}-")
    )
    params = "satellite: 18, channel: 6"
    if sector is not None:
        params += f", product: ABI-L2-CMIPM, sector: {sector}"
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(f"""name: goes-scene
sources:
  - dataset: noaa:goes-abi
    start: 2024-05-06T12:00Z
    end: 2024-05-06T12:05Z
    params: {{{params}}}
""")
    with respx.mock() as mock:
        listed = mock.get(LIST_URL).respond(200, text=listing([(key, len(DATA))]))
        downloaded = mock.get(s3.https_url("noaa-goes18", key)).respond(200, content=DATA)
        first = pull(manifest, root=tmp_path / "cache")
        item = first.fetched[0]
        assert item.provenance.source_url == f"s3://noaa-goes18/{key}"
        assert item.path.read_bytes() == DATA
        assert pull(manifest, root=tmp_path / "cache").fetched[0].from_cache
        item.path.unlink()
        restored = pull(manifest, root=tmp_path / "cache")
        assert restored.from_lockfile and restored.lockfile == first.lockfile
        assert listed.call_count == 1 and downloaded.call_count == 2
    assert verify(manifest, root=tmp_path / "cache") == []
    item.path.unlink()
    with respx.mock() as mock, pytest.raises(ChecksumMismatch):
        mock.get(s3.https_url("noaa-goes18", key)).respond(200, content=b"revised bytes")
        pull(manifest, root=tmp_path / "cache")
