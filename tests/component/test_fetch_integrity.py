from pathlib import Path

import httpx
import pytest
import respx

from usdata import build_query, get, provenance
from usdata.fetch import ChecksumMismatch, fetch, fetch_asset
from usdata.models import Asset, Protocol
from usdata.providers.noaa.ghcnd import DATA_URL


def test_cached_asset_honors_new_checksum_and_preserves_old_file(tmp_path: Path) -> None:
    ds = get("noaa:ghcn-daily")
    asset = Asset(id="data", dataset_id=ds.id, href=DATA_URL, protocol=Protocol.HTTP)
    with respx.mock() as mock:
        data = mock.get(DATA_URL).respond(200, content=b"original")
        original = fetch_asset(ds, asset, root=tmp_path)
        pinned = asset.model_copy(update={"checksum": "sha256:" + "0" * 64})
        with pytest.raises(ChecksumMismatch):
            fetch_asset(ds, pinned, root=tmp_path)
        assert data.call_count == 2
    assert original.path.read_bytes() == b"original"
    assert provenance.read(original.path) == original.provenance
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.parametrize("fail", [False, True])
def test_fetch_reuses_and_closes_owned_client(tmp_path: Path, monkeypatch, fail: bool) -> None:
    clients: list[httpx.Client] = []
    requests: list[httpx.Request] = []

    def respond(request):
        requests.append(request)
        return httpx.Response(500 if fail else 200, content=b"data")

    def make_client():
        client = httpx.Client(transport=httpx.MockTransport(respond))
        clients.append(client)
        return client

    monkeypatch.setattr("usdata.protocols.http.client", make_client)
    query = build_query(start="2024-01-01", end="2024-01-02", stations=[f"S{i}" for i in range(51)])
    if fail:
        with pytest.raises(httpx.HTTPStatusError):
            fetch(get("noaa:ghcn-daily"), query, root=tmp_path)
    else:
        assert len(fetch(get("noaa:ghcn-daily"), query, root=tmp_path)) == 2
    assert len(requests) == (3 if fail else 2)
    assert len(clients) == 1 and clients[0].is_closed
