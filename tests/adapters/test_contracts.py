"""Shared behavioral contracts; dataset-specific wire semantics stay in adapter tests."""

from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path
from typing import cast

import httpx
import pytest

from usdata.models import Query, Status
from usdata.protocols import s3
from usdata.providers import Provider, load_adapter
from usdata.providers.base import QueryError
from usdata.providers.noaa.coastwatch import BASE, DATASET
from usdata.providers.noaa.storm_events import DIRECTORY_URL
from usdata.providers.usgs.daily import ITEMS_URL
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.l2
DATA = b"source bytes\n"
CASES = {
    "noaa:ghcn-daily": {"stations": "USW00013967"},
    "noaa:coops-water-levels": {"station": "8518750", "datum": "MLLW"},
    "noaa:gsom": {"stations": "USW00013967"},
    "noaa:gsoy": {"stations": "USW00013967"},
    "noaa:climate-normals": {"stations": "USW00013967"},
    "noaa:nexrad-level2": {"site": "KTLX"},
    "noaa:goes-abi": {"satellite": 18, "channel": 6},
    "noaa:coastwatch-sst": {"bbox": (-80.08, 30.02, -80.02, 30.08)},
    "noaa:storm-events": {},
    "usgs:water-daily": {"sites": "07164500"},
}
S3_KEYS = {
    "noaa:nexrad-level2": "2024/05/06/KTLX/KTLX20240506_120100_V06",
    "noaa:goes-abi": "ABI-L2-CMIPC/2024/127/12/"
    "OR_ABI-L2-CMIPC-M6C06_G18_s20241271201181_e20241271203560_c20241271204021.nc",
}
STORM_NAME = "StormEvents_details-ftp_v1.0_d2024_c20260323.csv.gz"


def query(dataset_id: str) -> Query:
    return build_query(start="2024-05-06T12:00Z", end="2024-05-06T12:05Z", **CASES[dataset_id])


def test_every_available_adapter_has_a_contract_scenario() -> None:
    available = {ds.id for ds in default_registry() if ds.status is Status.AVAILABLE}
    assert set(CASES) == available


@pytest.mark.parametrize("dataset_id", CASES)
@pytest.mark.parametrize("injected", [False, True], ids=["owned", "injected"])
@pytest.mark.parametrize("fail", [False, True], ids=["success", "fetch-error"])
def test_adapter_contract(dataset_id, injected, fail, tmp_path, monkeypatch) -> None:
    data = (
        b"Date Time, Water Level, Sigma, O or I (for verified), F, R, L, Quality \n"
        b"2024-05-06 12:00,1.765,0.06,0,0,0,0,v\n"
        if dataset_id == "noaa:coops-water-levels"
        else DATA
    )
    downloads: set[str] = set()
    requests: list[httpx.Request] = []
    clients: list[httpx.Client] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
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
        if str(request.url) == DIRECTORY_URL:
            return httpx.Response(
                200,
                text=f'<table><tr><td><a href="{STORM_NAME}">{STORM_NAME}</a></td>'
                f'<td>2026-03-23</td><td align="right">{len(data)}</td></tr></table>',
            )
        if str(request.url).startswith(ITEMS_URL) and request.url.params.get("f") == "json":
            return httpx.Response(200, json={"features": [{"id": "a"}], "links": []})
        if str(request.url) == f"{BASE}/info/{DATASET}/index.csv":
            info = (Path(__file__).parents[1] / "fixtures/coastwatch-info.csv").read_text()
            return httpx.Response(200, text=info)
        if str(request.url) == f"{BASE}/griddap/{DATASET}.csv?time":
            return httpx.Response(200, text="time\nUTC\n2024-05-06T12:00:00Z\n")
        raise AssertionError(f"unconfigured contract request: {request.url}")

    def make_client():
        client = httpx.Client(transport=httpx.MockTransport(respond))
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
def test_invalid_query_rejected_without_creating_client(dataset_id, monkeypatch) -> None:
    def unexpected_client():
        raise AssertionError("invalid query must fail before allocating a client")

    monkeypatch.setattr("usdata.protocols.http.client", unexpected_client)
    invalid = query(dataset_id).model_copy(
        update={"params": {**query(dataset_id).params, "typo": 1}}
    )
    with load_adapter(default_registry().get(dataset_id)) as adapter, pytest.raises(QueryError):
        adapter.list_assets(invalid)
