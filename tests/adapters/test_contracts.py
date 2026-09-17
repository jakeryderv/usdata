"""Shared behavioral contracts; dataset-specific wire semantics stay in adapter tests.

The assertions themselves live in `usdata.testing`, so an adapter written
outside this repository runs the same ones. This module supplies the scenario
per dataset and the mock transport that answers it.
"""

import pkgutil
from collections.abc import Callable
from datetime import timedelta
from importlib import import_module
from pathlib import Path
from typing import cast

import httpx
import pytest

from usdata import providers, testing
from usdata.models import Query, Status
from usdata.providers import Provider, load_adapter
from usdata.providers.noaa.coastwatch import BASE, DATASET
from usdata.providers.noaa.hurdat2 import DIRECTORY_URL as HURDAT_URL
from usdata.providers.noaa.spc import PAGE_URL as SPC_PAGE
from usdata.providers.noaa.storm_events import DIRECTORY_URL
from usdata.providers.usgs.daily import ITEMS_URL
from usdata.providers.usgs.earthquakes import COUNT_URL
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.l2
DATA = b"source bytes\n"
CASES = {
    "noaa:ghcn-daily": {"stations": "USW00013967"},
    "noaa:coops-water-levels": {"station": "8518750", "datum": "MLLW"},
    "noaa:coops-tide-predictions": {"station": "8518750", "datum": "MLLW"},
    "noaa:gsom": {"stations": "USW00013967"},
    "noaa:gsoy": {"stations": "USW00013967"},
    "noaa:climate-normals": {"stations": "USW00013967"},
    "noaa:lcd": {"stations": "72353013967"},
    "noaa:nexrad-level2": {"site": "KTLX"},
    "noaa:nexrad-level3": {"site": "KTLX", "products": "N0B"},
    "noaa:goes-abi": {"satellite": 18, "channel": 6},
    "noaa:goes-glm": {"satellite": 16},
    "noaa:mrms": {"product": "RotationTrackML30min_00.50"},
    "noaa:hrrr": {"cycle": 12, "forecast_hour": 0},
    "noaa:gfs": {"cycle": 12, "forecast_hour": 0, "resolution": "1p00"},
    "noaa:coastwatch-sst": {"bbox": (-80.08, 30.02, -80.02, 30.08)},
    "noaa:storm-events": {},
    "noaa:spc-tornado-reports": {},
    "noaa:hurdat2": {"basin": "pacific"},
    "usgs:water-daily": {"sites": "07164500"},
    "usgs:earthquakes": {"min_magnitude": "2.5"},
    "noaa:rap": {"cycle": 12, "forecast_hour": 0},
    "noaa:nbm": {"cycle": 12, "forecast_hour": 1},
}
S3_KEYS = {
    "noaa:nexrad-level2": "2024/05/06/KTLX/KTLX20240506_120100_V06",
    "noaa:nexrad-level3": "TLX_N0B_2024_05_06_12_01_00",
    "noaa:goes-abi": "ABI-L2-CMIPC/2024/127/12/"
    "OR_ABI-L2-CMIPC-M6C06_G18_s20241271201181_e20241271203560_c20241271204021.nc",
    "noaa:goes-glm": "GLM-L2-LCFA/2024/127/12/"
    "OR_GLM-L2-LCFA_G16_s20241271200000_e20241271200200_c20241271200213.nc",
    "noaa:mrms": "CONUS/RotationTrackML30min_00.50/20240506/"
    "MRMS_RotationTrackML30min_00.50_20240506-120000.grib2.gz",
    "noaa:hrrr": "hrrr.20240506/conus/hrrr.t12z.wrfsfcf00.grib2",
    "noaa:gfs": "gfs.20240506/12/atmos/gfs.t12z.pgrb2.1p00.f000",
    "noaa:rap": "rap.20240506/rap.t12z.awp130pgrbf00.grib2",
    "noaa:nbm": "blend.20240506/12/core/blend.t12z.core.f001.co.grib2",
}
STORM_NAME = "StormEvents_details-ftp_v1.0_d2024_c20260323.csv.gz"
HURDAT_NAME = "hurdat2-nepac-1949-2025-02272026.txt"
# HURDAT2 publishes the complete record per basin, so it rejects a time filter.
UNTIMED = {"noaa:hurdat2"}
WINDOW = {"start": "2024-05-06T12:00Z", "end": "2024-05-06T12:05Z"}
# The window each adapter enforces, named where the adapter defines or imports it. Reading
# the constants is why this module imports provider packages, as the adapter tests do.
WINDOW_CONSTANTS = {
    "noaa:nexrad-level2": ("usdata.providers.noaa.nexrad", "MAX_WINDOW"),
    "noaa:nexrad-level3": ("usdata.providers.noaa.nexrad_level3", "MAX_WINDOW"),
    "noaa:goes-abi": ("usdata.providers.noaa.goes", "MAX_WINDOW"),
    "noaa:goes-glm": ("usdata.providers.noaa.glm", "MAX_WINDOW"),
    "noaa:mrms": ("usdata.providers.noaa.mrms", "MAX_WINDOW"),
    "noaa:hrrr": ("usdata.providers.noaa.hrrr", "MAX_WINDOW"),
    # GFS, RAP, and NBM inherit their window from the shared ModelRuns base in the HRRR module.
    "noaa:gfs": ("usdata.providers.noaa.hrrr", "MAX_WINDOW"),
    "noaa:rap": ("usdata.providers.noaa.hrrr", "MAX_WINDOW"),
    "noaa:nbm": ("usdata.providers.noaa.hrrr", "MAX_WINDOW"),
    "noaa:coops-water-levels": ("usdata.providers.noaa.coops", "MAX_INTERVAL"),
    "noaa:coops-tide-predictions": ("usdata.providers.noaa.coops", "MAX_PREDICTION_INTERVAL"),
}


def query(dataset_id: str) -> Query:
    window = {} if dataset_id in UNTIMED else WINDOW
    return build_query(**window, **CASES[dataset_id])


def timed_query(dataset_id: str) -> Query:
    """The scenario query with a window, even for an adapter that refuses one."""
    return build_query(**WINDOW, **CASES[dataset_id])


def adapter_factory(dataset_id: str) -> testing.AdapterFactory:
    """Build the adapter with its own client, or with one the caller supplies."""

    def build(client: httpx.Client | None = None) -> Provider:
        dataset = default_registry().get(dataset_id)
        adapter = load_adapter(dataset)
        if client is None:
            return adapter
        constructor = cast(Callable[..., Provider], type(adapter))
        return constructor(dataset, client=client)

    return build


def contract_data(dataset_id: str) -> bytes:
    if dataset_id == "noaa:coops-tide-predictions":
        return b"Date Time, Prediction\n2024-05-06 12:00,0.719\n"
    if dataset_id == "noaa:coops-water-levels":
        return (
            b"Date Time, Water Level, Sigma, O or I (for verified), F, R, L, Quality \n"
            b"2024-05-06 12:00,1.765,0.06,0,0,0,0,v\n"
        )
    return DATA


def contract_transport(
    dataset_id: str, downloads: set[str], *, fail: bool = False
) -> httpx.MockTransport:
    """Answer the listing requests each adapter makes for ``query(dataset_id)``."""
    data = contract_data(dataset_id)

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        if str(request.url) in downloads:
            return httpx.Response(503 if fail else 200, content=data)
        if dataset_id in S3_KEYS and request.url.params.get("list-type") == "2":
            key = S3_KEYS[dataset_id]
            return httpx.Response(
                200,
                text='<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                f"<IsTruncated>false</IsTruncated><Contents><Key>{key}</Key>"
                f"<Size>{len(data)}</Size></Contents></ListBucketResult>",
            )
        if str(request.url) == HURDAT_URL:
            return httpx.Response(
                200, text=f'<table><tr><td><a href="{HURDAT_NAME}">x</a></td></tr></table>'
            )
        if str(request.url) == SPC_PAGE:
            return httpx.Response(
                200,
                text='<table><tr><td><a href="data/2024_torn.csv">x (0.2 mb)</a></td></tr></table>',
            )
        if str(request.url) == DIRECTORY_URL:
            return httpx.Response(
                200,
                text=f'<table><tr><td><a href="{STORM_NAME}">{STORM_NAME}</a></td>'
                f'<td>2026-03-23</td><td align="right">{len(data)}</td></tr></table>',
            )
        if str(request.url).startswith(COUNT_URL):
            return httpx.Response(200, text="1")
        if str(request.url).startswith(ITEMS_URL) and request.url.params.get("f") == "json":
            first = request.url.params.get("offset") == "0"
            return httpx.Response(200, json={"features": [{"id": "a"}] if first else []})
        if str(request.url) == f"{BASE}/info/{DATASET}/index.csv":
            info = (Path(__file__).parents[1] / "fixtures/coastwatch-info.csv").read_text()
            return httpx.Response(200, text=info)
        if str(request.url) == f"{BASE}/griddap/{DATASET}.csv?time":
            return httpx.Response(200, text="time\nUTC\n2024-05-06T12:00:00Z\n")
        raise AssertionError(f"unconfigured contract request: {request.url}")

    return httpx.MockTransport(respond)


def client_factory(
    dataset_id: str, downloads: set[str], *, fail: bool = False
) -> testing.ClientFactory:
    def build() -> httpx.Client:
        return httpx.Client(transport=contract_transport(dataset_id, downloads, fail=fail))

    return build


def test_every_available_adapter_has_a_contract_scenario() -> None:
    available = {ds.id for ds in default_registry() if ds.status is Status.AVAILABLE}
    assert set(CASES) == available


@pytest.mark.parametrize("dataset_id", CASES)
@pytest.mark.parametrize("injected", [False, True], ids=["owned", "injected"])
@pytest.mark.parametrize("fail", [False, True], ids=["success", "fetch-error"])
def test_adapter_contract(dataset_id, injected, fail, tmp_path) -> None:
    downloads: set[str] = set()
    testing.check_fetch_lifecycle(
        adapter_factory(dataset_id),
        query(dataset_id),
        client_factory(dataset_id, downloads, fail=fail),
        expected_bytes=contract_data(dataset_id),
        arm_download=downloads.add,
        injected=injected,
        fail=fail,
        work_dir=tmp_path,
    )


@pytest.mark.parametrize("dataset_id", CASES)
def test_declared_params_accepted_and_an_undeclared_one_rejected(dataset_id) -> None:
    testing.check_declared_params(adapter_factory(dataset_id), query(dataset_id))


@pytest.mark.parametrize("dataset_id", CASES)
def test_a_declared_model_is_the_whole_parameter_declaration(dataset_id) -> None:
    testing.check_params_declaration(adapter_factory(dataset_id))


@pytest.mark.parametrize("dataset_id", CASES)
def test_text_rejected_by_every_adapter_without_creating_client(dataset_id) -> None:
    testing.check_text_refused(adapter_factory(dataset_id), query(dataset_id))


@pytest.mark.parametrize("dataset_id", sorted(set(CASES) - UNTIMED))
def test_naive_and_offset_bounds_resolve_like_utc(dataset_id) -> None:
    testing.check_utc_equivalence(
        adapter_factory(dataset_id), query(dataset_id), client_factory(dataset_id, set())
    )


@pytest.mark.parametrize("dataset_id", CASES)
def test_invalid_query_rejected_without_creating_client(dataset_id) -> None:
    testing.check_invalid_params_refused(adapter_factory(dataset_id), query(dataset_id))


@pytest.mark.parametrize("dataset_id", CASES)
def test_declared_capabilities_are_the_ones_the_adapter_honours(dataset_id) -> None:
    testing.check_declared_capabilities(
        default_registry().get(dataset_id),
        adapter_factory(dataset_id),
        query(dataset_id),
        timed_query(dataset_id),
    )


def test_declared_windows_equal_the_windows_the_adapters_enforce() -> None:
    registry = default_registry()
    for dataset_id, (module_name, constant) in WINDOW_CONSTANTS.items():
        limits = registry.get(dataset_id).limits
        assert limits is not None and limits.max_window is not None, dataset_id
        assert limits.max_window == getattr(import_module(module_name), constant), dataset_id


def test_every_adapter_window_constant_is_declared_in_the_registry() -> None:
    """A window a new adapter enforces has to reach the registry, not only the module."""
    found: set[tuple[str, str]] = set()
    for info in pkgutil.walk_packages(providers.__path__, f"{providers.__name__}."):
        module = import_module(info.name)
        found |= {
            (info.name, name)
            for name, value in vars(module).items()
            if name.startswith("MAX_") and isinstance(value, timedelta)
        }
    assert found == set(WINDOW_CONSTANTS.values())


def test_partial_fetch_is_declared_exactly_where_the_adapter_takes_messages() -> None:
    """The capability is a promise about a query surface, so the two must agree."""
    registry = default_registry()
    assert {ds.id for ds in registry if ds.capabilities.partial_fetch} == {
        "noaa:hrrr",
        "noaa:gfs",
        "noaa:rap",
        "noaa:nbm",
    }
    for dataset_id in CASES:
        with adapter_factory(dataset_id)() as adapter:
            declares = testing.PARTIAL_PARAM in adapter.accepted_params
            assert declares is registry.get(dataset_id).capabilities.partial_fetch, dataset_id
