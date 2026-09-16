from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

import httpx
import pytest
import respx

from usdata.models import ByteRange
from usdata.protocols import http

URL = "https://example.test/data"
OBJECT = b"".join(bytes([value]) * 20 for value in range(1, 6))
ETAG = "81198a73ad430c73adfbe3335421ea99"
TOTAL = len(OBJECT)


def parts(*pairs: tuple[int, int]) -> list[ByteRange]:
    return [ByteRange(start=start, end=end) for start, end in pairs]


def serve_ranges(
    *,
    status: int = 206,
    etag: str = ETAG,
    content_range: str | None = None,
    body: bytes | None = None,
):
    """Answer a range request the way S3 does, or in one of the ways it must not."""

    def respond(request: httpx.Request) -> httpx.Response:
        if request.headers.get("If-Match") != etag:
            return httpx.Response(412)
        start, end = (int(value) for value in request.headers["Range"][6:].split("-"))
        chunk = OBJECT if status == 200 else OBJECT[start : end + 1]
        headers = {}
        if status != 200:
            headers["Content-Range"] = content_range or f"bytes {start}-{end}/{TOTAL}"
        return httpx.Response(status, content=body if body is not None else chunk, headers=headers)

    return respond


@pytest.mark.l2
def test_one_get_per_run_with_range_and_if_match(tmp_path: Path) -> None:
    dest = tmp_path / "part.grib2"
    with respx.mock() as mock, http.client() as client:
        route = mock.get(URL)
        route.side_effect = serve_ranges()
        assert (
            http.download_ranges(
                URL, dest, parts((0, 19), (60, 79)), etag=ETAG, total=TOTAL, http=client
            )
            == dest
        )
    assert dest.read_bytes() == OBJECT[0:20] + OBJECT[60:80]
    assert route.call_count == 2
    assert [call.request.headers["Range"] for call in route.calls] == [
        "bytes=0-19",
        "bytes=60-79",
    ]
    assert {call.request.headers["If-Match"] for call in route.calls} == {ETAG}


@pytest.mark.l2
def test_adjacent_ranges_become_one_request(tmp_path: Path) -> None:
    dest = tmp_path / "part.grib2"
    with respx.mock() as mock, http.client() as client:
        route = mock.get(URL)
        route.side_effect = serve_ranges()
        http.download_ranges(
            URL, dest, parts((20, 39), (40, 59), (80, 99)), etag=ETAG, total=TOTAL, http=client
        )
    assert dest.read_bytes() == OBJECT[20:60] + OBJECT[80:100]
    assert [call.request.headers["Range"] for call in route.calls] == [
        "bytes=20-59",
        "bytes=80-99",
    ]


@pytest.mark.l2
@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    [
        ({"status": 200}, http.RangeNotHonored, "offered the whole object"),
        ({"etag": "other"}, http.ObjectChanged, "was republished"),
        ({"content_range": "bytes 0-4/500"}, http.RangeNotHonored, "Content-Range"),
        ({"content_range": "somewhere in the middle"}, http.RangeNotHonored, "Content-Range"),
        ({"body": b"short"}, http.RangeNotHonored, "not 20"),
    ],
)
def test_a_range_that_is_not_honoured_writes_nothing_and_is_not_retried(
    tmp_path: Path, kwargs, error, message
) -> None:
    dest = tmp_path / "part.grib2"
    dest.write_bytes(b"existing")
    with respx.mock() as mock, http.client() as client:
        route = mock.get(URL)
        route.side_effect = serve_ranges(**kwargs)
        with pytest.raises(error, match=message):
            http.download_ranges(
                URL, dest, parts((0, 19), (60, 79)), etag=ETAG, total=TOTAL, http=client
            )
    assert route.call_count == 1
    assert dest.read_bytes() == b"existing" and list(tmp_path.iterdir()) == [dest]


@pytest.mark.l2
def test_a_transient_failure_restarts_every_run(tmp_path: Path, monkeypatch) -> None:
    dest = tmp_path / "part.grib2"
    monkeypatch.setattr(http, "sleep", lambda delay: None)
    calls: list[str] = []
    honour = serve_ranges()

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers["Range"])
        if len(calls) == 2:
            return httpx.Response(503)
        return honour(request)

    with respx.mock() as mock, http.client() as client:
        mock.get(URL).side_effect = respond
        http.download_ranges(
            URL, dest, parts((0, 19), (60, 79)), etag=ETAG, total=TOTAL, http=client
        )
    assert calls == ["bytes=0-19", "bytes=60-79", "bytes=0-19", "bytes=60-79"]
    assert dest.read_bytes() == OBJECT[0:20] + OBJECT[60:80]


@pytest.mark.parametrize(
    "ranges",
    [[], [(60, 79), (0, 19)], [(0, 19), (10, 29)], [(0, 19), (0, 19)], [(90, 120)]],
)
def test_ranges_must_ascend_inside_the_object(tmp_path: Path, ranges) -> None:
    dest = tmp_path / "part.grib2"
    with respx.mock() as mock:
        with pytest.raises(ValueError):
            http.download_ranges(URL, dest, parts(*ranges), etag=ETAG, total=TOTAL)
        assert not mock.calls
    assert not dest.exists()


def test_contiguous_runs_merges_only_what_touches() -> None:
    merged = http.contiguous_runs(parts((0, 9), (10, 19), (30, 39)), 100)
    assert [(run.start, run.end) for run in merged] == [(0, 19), (30, 39)]


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


@pytest.mark.l2
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


@pytest.mark.l2
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


def test_head_reports_headers_and_retries_transient_status(monkeypatch) -> None:
    monkeypatch.setattr(http, "sleep", lambda delay: None)
    with respx.mock() as mock, http.client() as client:
        route = mock.head(URL)
        route.side_effect = [
            httpx.Response(503),
            httpx.Response(200, headers={"Content-Length": "151717165", "ETag": f'"{ETAG}"'}),
        ]
        response = http.head(URL, client)
    assert route.call_count == 2
    assert response.headers["Content-Length"] == "151717165"
