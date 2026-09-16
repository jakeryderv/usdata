"""Shared behavioral contracts; dataset-specific wire semantics stay in adapter tests."""

import pkgutil
import re
from collections.abc import Callable
from contextlib import nullcontext
from datetime import timedelta, timezone
from importlib import import_module
from pathlib import Path
from typing import cast

import httpx
import pytest

from usdata import providers
from usdata.models import BBox, Query, Status, TimeRange
from usdata.protocols import s3
from usdata.providers import Provider, load_adapter
from usdata.providers.base import QueryError, QueryField
from usdata.providers.noaa.coastwatch import BASE, DATASET
from usdata.providers.noaa.hurdat2 import DIRECTORY_URL as HURDAT_URL
from usdata.providers.noaa.spc import PAGE_URL as SPC_PAGE
from usdata.providers.noaa.storm_events import DIRECTORY_URL
from usdata.providers.usgs.daily import ITEMS_URL
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
}
STORM_NAME = "StormEvents_details-ftp_v1.0_d2024_c20260323.csv.gz"
HURDAT_NAME = "hurdat2-nepac-1949-2025-02272026.txt"
# HURDAT2 publishes the complete record per basin, so it rejects a time filter.
UNTIMED = {"noaa:hurdat2"}
WINDOW = {"start": "2024-05-06T12:00Z", "end": "2024-05-06T12:05Z"}
PROBE_BBOX = BBox(west=-97.7, south=35.2, east=-97.2, north=35.7)
# How Provider.reject names each field it refuses, which is what a refusal is read from.
REFUSED = {"bbox": "location/bbox", "variables": "variables", "time": "start/end"}
# Parameters naming a station or site. A bbox stands in for one wherever they are declared.
SELECTORS = frozenset({"site", "sites", "station", "stations", "nearest"})
# The window each adapter enforces, named where the adapter defines or imports it. Reading
# the constants is why this module imports provider packages, as the adapter tests do.
WINDOW_CONSTANTS = {
    "noaa:nexrad-level2": ("usdata.providers.noaa.nexrad", "MAX_WINDOW"),
    "noaa:nexrad-level3": ("usdata.providers.noaa.nexrad_level3", "MAX_WINDOW"),
    "noaa:goes-abi": ("usdata.providers.noaa.goes", "MAX_WINDOW"),
    "noaa:goes-glm": ("usdata.providers.noaa.glm", "MAX_WINDOW"),
    "noaa:mrms": ("usdata.providers.noaa.mrms", "MAX_WINDOW"),
    "noaa:hrrr": ("usdata.providers.noaa.hrrr", "MAX_WINDOW"),
    # GFS inherits its window from the shared ModelRuns base in the HRRR module.
    "noaa:gfs": ("usdata.providers.noaa.hrrr", "MAX_WINDOW"),
    "noaa:coops-water-levels": ("usdata.providers.noaa.coops", "MAX_INTERVAL"),
    "noaa:coops-tide-predictions": ("usdata.providers.noaa.coops", "MAX_PREDICTION_INTERVAL"),
}


def query(dataset_id: str) -> Query:
    window = {} if dataset_id in UNTIMED else WINDOW
    return build_query(**window, **CASES[dataset_id])


def timed_query(dataset_id: str) -> Query:
    """The scenario query with a window, even for an adapter that refuses one."""
    return build_query(**WINDOW, **CASES[dataset_id])


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


def test_every_available_adapter_has_a_contract_scenario() -> None:
    available = {ds.id for ds in default_registry() if ds.status is Status.AVAILABLE}
    assert set(CASES) == available


@pytest.mark.parametrize("dataset_id", CASES)
@pytest.mark.parametrize("injected", [False, True], ids=["owned", "injected"])
@pytest.mark.parametrize("fail", [False, True], ids=["success", "fetch-error"])
def test_adapter_contract(dataset_id, injected, fail, tmp_path, monkeypatch) -> None:
    data = contract_data(dataset_id)
    downloads: set[str] = set()
    clients: list[httpx.Client] = []

    def make_client():
        client = httpx.Client(transport=contract_transport(dataset_id, downloads, fail=fail))
        clients.append(client)
        return client

    monkeypatch.setattr("usdata.protocols.http.client", make_client)
    monkeypatch.setenv("USDATA_CACHE_DIR", str(tmp_path / "forbidden-cache"))
    dataset = default_registry().get(dataset_id)
    adapter = load_adapter(dataset)
    assert clients == []  # Construction is lazy.
    supplied = make_client() if injected else None
    if supplied is not None:
        constructor = cast(Callable[..., Provider], type(adapter))
        adapter = constructor(dataset, client=supplied)
    try:
        with pytest.raises(httpx.HTTPStatusError) if fail else nullcontext(), adapter:
            first = adapter.list_assets(query(dataset_id))
            assert len(first) == 1
            assert first == adapter.list_assets(query(dataset_id))
            assert {a.dataset_id for a in first} == {dataset_id}
            assert len({a.id for a in first}) == len(first)
            assert all(a.id and a.href and a.time and a.time.start for a in first)
            assert all(a.size is None or a.size == len(data) for a in first)
            assert list(tmp_path.iterdir()) == []  # Listing never writes cache/provenance.
            asset = first[0]
            downloads.add(
                str(
                    httpx.URL(
                        s3.https_url(*s3.parse_s3_url(asset.href))
                        if asset.href.startswith("s3://")
                        else asset.href
                    )
                )
            )
            dest = tmp_path / "chosen-output"
            assert adapter.fetch(asset, dest) == dest
            assert dest.read_bytes() == data
            assert list(tmp_path.iterdir()) == [dest]  # No provider-owned sidecars.
            assert len(clients) == 1
        if fail:
            assert list(tmp_path.iterdir()) == []
        assert len(clients) == 1
        assert clients[0].is_closed is not injected
        adapter.close()  # Repeated cleanup remains safe.
        assert clients[0].is_closed is not injected
    finally:
        if supplied is not None:
            supplied.close()


@pytest.mark.parametrize("dataset_id", CASES)
def test_declared_params_accepted_and_an_undeclared_one_rejected(dataset_id, monkeypatch) -> None:
    """Every declared key is accepted; a key outside the declaration is named as unsupported.

    This probes one undeclared key, so it catches an adapter that narrowed its
    check below the declaration, not one that quietly widened it to keys nobody
    declared. Only reading ``accepted_params`` in the rejection gives that.
    """

    def unexpected_client():
        raise AssertionError("parameter validation must precede any transport")

    monkeypatch.setattr("usdata.protocols.http.client", unexpected_client)
    with load_adapter(default_registry().get(dataset_id)) as adapter:
        declared = dict(adapter.accepted_params)
        assert all(
            description.strip() and "\n" not in description for description in declared.values()
        )
        probe = query(dataset_id).model_copy(
            update={"params": {**dict.fromkeys(declared, "probe"), "unknown-key": "probe"}}
        )
        with pytest.raises(QueryError) as error:
            adapter.list_assets(probe)
    reported = re.search(r"unsupported .*params: (.+)$", str(error.value))
    assert reported is not None, f"{dataset_id} rejected a declared parameter: {error.value}"
    assert reported[1] == "unknown-key"


def test_a_declared_model_is_the_whole_parameter_declaration() -> None:
    """The model is the only declaration form, and no model means no accepted parameter.

    An adapter either declares a model that forbids extras and fills
    ``accepted_params``, or declares none and accepts nothing at all.
    """
    for dataset_id in CASES:
        with load_adapter(default_registry().get(dataset_id)) as adapter:
            model = adapter.params_model
            if model is None:
                assert dict(adapter.accepted_params) == {}, dataset_id
                continue
            assert model.model_config.get("extra") == "forbid", dataset_id
            assert set(adapter.accepted_params) == set(model.model_fields), dataset_id


@pytest.mark.parametrize("dataset_id", CASES)
def test_text_rejected_by_every_adapter_without_creating_client(dataset_id, monkeypatch) -> None:
    """Free text searches the registry; no adapter can honour it, so none may ignore it."""

    def unexpected_client():
        raise AssertionError("an unsupported query field must fail before any transport")

    monkeypatch.setattr("usdata.protocols.http.client", unexpected_client)
    probe = query(dataset_id).model_copy(update={"text": "precipitation"})
    with load_adapter(default_registry().get(dataset_id)) as adapter, pytest.raises(QueryError):
        adapter.list_assets(probe)


@pytest.mark.parametrize("dataset_id", sorted(set(CASES) - UNTIMED))
def test_naive_and_offset_bounds_resolve_like_utc(dataset_id, monkeypatch) -> None:
    """Naive bounds mean UTC and aware ones convert, whatever the adapter's own time logic."""
    monkeypatch.setattr(
        "usdata.protocols.http.client",
        lambda: httpx.Client(transport=contract_transport(dataset_id, set())),
    )
    aware = query(dataset_id)
    assert aware.time and aware.time.start and aware.time.end
    naive = aware.model_copy(
        update={
            "time": TimeRange(
                start=aware.time.start.replace(tzinfo=None),
                end=aware.time.end.replace(tzinfo=None),
            )
        }
    )
    eastern = timezone(timedelta(hours=-5))
    shifted = aware.model_copy(
        update={
            "time": TimeRange(
                start=aware.time.start.astimezone(eastern), end=aware.time.end.astimezone(eastern)
            )
        }
    )
    with load_adapter(default_registry().get(dataset_id)) as adapter:
        expected = adapter.list_assets(aware)
        assert len(expected) == 1
        assert adapter.list_assets(naive) == expected
        assert adapter.list_assets(shifted) == expected
    assert all(a.time and a.time.start and a.time.start.utcoffset() is not None for a in expected)


@pytest.mark.parametrize("dataset_id", CASES)
def test_invalid_query_rejected_without_creating_client(dataset_id, monkeypatch) -> None:
    def unexpected_client():
        raise AssertionError("invalid query must fail before allocating a client")

    monkeypatch.setattr("usdata.protocols.http.client", unexpected_client)
    invalid = query(dataset_id).model_copy(
        update={"params": {**query(dataset_id).params, "typo": 1}}
    )
    with load_adapter(default_registry().get(dataset_id)) as adapter, pytest.raises(QueryError):
        adapter.list_assets(invalid)


class TransportReached(Exception):
    """Raised in place of a client, so a probe that got past validation is visible."""


def refuses(adapter: Provider, probe: Query, field: QueryField) -> bool:
    """Whether ``adapter`` refuses ``field`` outright, before reaching any transport.

    Only ``Provider.reject`` counts: its wording is the adapter's statement that
    the source cannot honour the field at all, as opposed to a rule about how
    one query combines its inputs.
    """
    try:
        adapter.list_assets(probe)
    except QueryError as error:
        message = str(error)
        return message.startswith(f"{adapter.dataset.id} does not support") and (
            REFUSED[field] in message
        )
    except TransportReached:
        return False
    return False


def demands_window(adapter: Provider, probe: Query) -> bool:
    """Whether ``adapter`` refuses a query that leaves start and end out."""
    try:
        adapter.list_assets(probe)
    except QueryError as error:
        return str(error) == f"{adapter.dataset.id} requires both start and end"
    except TransportReached:
        return False
    return False


@pytest.mark.parametrize("dataset_id", CASES)
def test_declared_capabilities_are_the_ones_the_adapter_honours(dataset_id, monkeypatch) -> None:
    """A declared capability is one the adapter accepts, and a false one is a field it refuses.

    The probes stop at validation: the transport raises instead of connecting,
    and reaching it counts as acceptance. A refusal is read from
    ``Provider.reject``, so a rule such as GHCN's "pass stations or a
    location/bbox, not both" is not one; it constrains how a query combines its
    inputs rather than what the source can do.

    A bbox means two things. For a gridded or whole-file source it asks for a
    spatial subset, and the adapter either honours it or refuses it. For a
    source that selects by station or site -- one whose parameters name them --
    a bbox only chooses which stations or sites to ask for, and each asset still
    arrives whole, so accepting one proves nothing about subsetting. Those
    adapters are held to the refusal direction alone: refusing a bbox still
    means ``spatial_subset`` is false, while accepting one may be either.

    ``temporal_subset`` is false only where the window plays no part, which
    HURDAT2 shows by refusing start/end. Such a dataset must not require a
    window either, having nothing to select with it.
    """

    def unexpected_client() -> httpx.Client:
        raise TransportReached(dataset_id)

    monkeypatch.setattr("usdata.protocols.http.client", unexpected_client)
    dataset = default_registry().get(dataset_id)
    declared = dataset.capabilities
    assert dataset.variables, f"{dataset_id} names no variable to probe with"
    variable = dataset.variables[0].name
    with load_adapter(dataset) as adapter:
        base = query(dataset_id)
        bbox_refused = refuses(adapter, base.model_copy(update={"bbox": PROBE_BBOX}), "bbox")
        variables_refused = refuses(
            adapter, base.model_copy(update={"variables": [variable]}), "variables"
        )
        time_refused = refuses(adapter, timed_query(dataset_id), "time")
        requires_window = demands_window(adapter, base.model_copy(update={"time": None}))
        selects_by_site = bool(SELECTORS & set(adapter.accepted_params))

    assert variables_refused is not declared.variable_subset, (
        f"{dataset_id} declares variable_subset={declared.variable_subset} and "
        f"{'refuses' if variables_refused else 'accepts'} variables={variable!r}"
    )
    assert time_refused is not declared.temporal_subset, (
        f"{dataset_id} declares temporal_subset={declared.temporal_subset} and "
        f"{'refuses' if time_refused else 'accepts'} a query window"
    )
    if not declared.temporal_subset:
        assert not requires_window, f"{dataset_id} requires a window it declares it cannot use"
    if bbox_refused:
        assert not declared.spatial_subset, f"{dataset_id} declares a bbox its adapter refuses"
    elif not selects_by_site:
        assert declared.spatial_subset, f"{dataset_id} accepts a bbox it does not declare"


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
