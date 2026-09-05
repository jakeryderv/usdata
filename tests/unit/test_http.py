from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

import httpx
import pytest
import respx

from usdata.protocols import http

URL = "https://example.test/data"


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_metadata_retries_transient_status(status: int, monkeypatch: pytest.MonkeyPatch) -> None:
    delays = []
    monkeypatch.setattr(http, "sleep", delays.append)
    with respx.mock() as mock, http.client() as client:
        route = mock.get(URL)
        route.side_effect = [httpx.Response(status), httpx.Response(200, json={"ok": True})]
        assert http.get(URL, client).json() == {"ok": True}
    assert route.call_count == 2 and delays == [0.5]


@pytest.mark.parametrize("status", [400, 401, 403, 404, 501])
def test_metadata_does_not_retry_permanent_status(status: int) -> None:
    with respx.mock() as mock, http.client() as client:
        route = mock.get(URL).respond(status)
        with pytest.raises(httpx.HTTPStatusError):
            http.get(URL, client)
    assert route.call_count == 1


def test_retries_exhausted_preserve_existing_file(tmp_path: Path, monkeypatch) -> None:
    dest = tmp_path / "data"
    dest.write_bytes(b"original")
    delays = []
    monkeypatch.setattr(http, "sleep", delays.append)
    with respx.mock() as mock:
        route = mock.get(URL).respond(503)
        with pytest.raises(httpx.HTTPStatusError):
            http.download(URL, dest)
    assert route.call_count == 3 and delays == [0.5, 1.0]
    assert dest.read_bytes() == b"original" and list(tmp_path.iterdir()) == [dest]


def test_retry_after_seconds_and_http_date(monkeypatch) -> None:
    delays = []
    monkeypatch.setattr(http, "sleep", delays.append)
    future = format_datetime(datetime.now(UTC) + timedelta(seconds=15), usegmt=True)
    with respx.mock() as mock, http.client() as client:
        route = mock.get(URL)
        route.side_effect = [
            httpx.Response(429, headers={"Retry-After": "3"}),
            httpx.Response(503, headers={"Retry-After": future}),
            httpx.Response(200),
        ]
        http.get(URL, client)
    assert delays[0] == 3 and 10 < delays[1] <= 15


def test_long_retry_after_is_not_retried_early(monkeypatch) -> None:
    delays = []
    monkeypatch.setattr(http, "sleep", delays.append)
    with respx.mock() as mock, http.client() as client:
        route = mock.get(URL).respond(429, headers={"Retry-After": "3600"})
        with pytest.raises(httpx.HTTPStatusError):
            http.get(URL, client)
    assert route.call_count == 1 and not delays


class InterruptedStream(httpx.SyncByteStream):
    def __iter__(self) -> Iterator[bytes]:
        yield b"partial"
        raise httpx.ReadError("connection lost")


def test_interrupted_download_restarts_without_partial_bytes(tmp_path: Path) -> None:
    dest = tmp_path / "data"
    with respx.mock() as mock, http.client() as client:
        route = mock.get(URL)
        route.side_effect = [
            httpx.Response(200, stream=InterruptedStream()),
            httpx.Response(200, content=b"complete"),
        ]
        http.download(URL, dest, client)
        assert not client.is_closed
    assert dest.read_bytes() == b"complete"
    assert route.call_count == 2 and list(tmp_path.iterdir()) == [dest]


@pytest.mark.parametrize(
    "error", [httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError]
)
def test_metadata_retries_transport_failures(error) -> None:
    with respx.mock() as mock, http.client() as client:
        route = mock.get(URL)
        route.side_effect = [error("temporary"), httpx.Response(200)]
        assert http.get(URL, client).status_code == 200
    assert route.call_count == 2
