"""Shared HTTP configuration and bounded retries for idempotent GET requests."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import sleep
from typing import Any, TypeVar

import httpx

from usdata import __version__, _progress
from usdata._files import staged_path
from usdata.models import ByteRange

USER_AGENT = f"usdata/{__version__} (+https://github.com/jakeryderv/usdata)"
DEFAULT_TIMEOUT = httpx.Timeout(10.0, read=120.0)
MAX_ATTEMPTS = 3
MAX_RETRY_DELAY = 30.0
RETRY_STATUS = {429, 500, 502, 503, 504}
PARTIAL_CONTENT = 206
CONTENT_RANGE = re.compile(r"bytes (\d+)-(\d+)/(\d+)")
AS_STORED = {"Accept-Encoding": "identity"}
"""Download headers: ask for no transfer compression, then write the body undecoded.

Many services gzip a response on the fly when asked, while an object stored with a
``Content-Encoding`` is served with it regardless. Asking for ``identity`` and
writing the raw body leaves the file byte for byte the object the source holds,
so its size and checksum match the listing.
"""
T = TypeVar("T")


class RangeNotHonored(httpx.HTTPError):
    """A range request came back as something other than exactly the bytes asked for.

    Serving the whole object instead of the requested interval, or answering with
    a ``Content-Range`` that does not match the request, would silently produce a
    file that is not the one the caller asked for, so it fails before any byte is
    written and is never retried.
    """


class ObjectChanged(RangeNotHonored):
    """The object was republished: its ETag no longer matches the one pinned (HTTP 412)."""


def client(**kwargs: Any) -> httpx.Client:
    """A configured client. Callers own its lifetime; use as a context manager."""
    kwargs.setdefault("headers", {"User-Agent": USER_AGENT})
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    kwargs.setdefault("follow_redirects", True)
    return httpx.Client(**kwargs)


def _as_stored(response: httpx.Response) -> Iterator[bytes]:
    """A downloaded body's bytes as the server sent them, not decoded (see ``AS_STORED``).

    A response built in memory, such as a mock transport returns, was read and
    decoded when it was made, and that content is all there is to write.
    """
    return response.iter_bytes() if response.is_stream_consumed else response.iter_raw()


def _retry_after(response: httpx.Response) -> float:
    value = response.headers.get("Retry-After", "")
    # str.isdigit accepts characters such as "²" that float() refuses.
    if value.isascii() and value.isdigit():
        return float(value)
    try:
        when = parsedate_to_datetime(value)
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        return max(0.0, (when - datetime.now(UTC)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _retry(operation: Callable[[], T]) -> T:
    for attempt in range(MAX_ATTEMPTS):
        try:
            return operation()
        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
            httpx.HTTPStatusError,
        ) as error:
            delay = 0.5 * 2**attempt
            if isinstance(error, httpx.HTTPStatusError):
                if error.response.status_code not in RETRY_STATUS:
                    raise
                delay = max(delay, _retry_after(error.response))
            # Never retry earlier than Retry-After; surface long waits to the caller.
            if attempt == MAX_ATTEMPTS - 1 or delay > MAX_RETRY_DELAY:
                raise
            sleep(delay)
    raise AssertionError("unreachable")


def get(
    url: str | httpx.URL,
    http: httpx.Client,
    *,
    before_attempt: Callable[[], object] | None = None,
    **kwargs: Any,
) -> httpx.Response:
    """GET a metadata page with bounded retries; the caller owns the client.

    ``before_attempt``, when given, is called before every attempt, retries
    included, after any backoff. A source that must space its requests passes
    its pacing here, so a retry cannot reach the service sooner than it allows.
    """

    def request() -> httpx.Response:
        if before_attempt is not None:
            before_attempt()
        response = http.get(url, **kwargs)
        response.raise_for_status()
        return response

    return _retry(request)


def head(url: str | httpx.URL, http: httpx.Client, **kwargs: Any) -> httpx.Response:
    """HEAD an object with the same bounded retries as ``get``; the caller owns the client."""

    def request() -> httpx.Response:
        response = http.head(url, **kwargs)
        response.raise_for_status()
        return response

    return _retry(request)


def contiguous_runs(ranges: Sequence[ByteRange], total: int) -> list[ByteRange]:
    """Merge ascending, non-overlapping ranges into the fewest intervals that cover them.

    Args:
        ranges: Byte ranges in ascending order, none overlapping another.
        total: Size of the object the ranges belong to; every range lies inside it.

    Returns:
        One range per contiguous run, in the same order.

    Raises:
        ValueError: The list is empty, out of order, overlapping, or past the object's end.
    """
    if not ranges:
        raise ValueError("a range request needs at least one byte range")
    runs: list[ByteRange] = []
    for part in ranges:
        if part.end >= total:
            raise ValueError(f"byte range {part.header} lies past the {total} byte object")
        if runs and part.start <= runs[-1].end:
            raise ValueError("byte ranges must ascend and must not overlap")
        if runs and part.start == runs[-1].end + 1:
            runs[-1] = ByteRange(start=runs[-1].start, end=part.end)
        else:
            runs.append(part)
    return runs


def _honored(response: httpx.Response, run: ByteRange, total: int, url: str) -> None:
    """Check a range response before a byte of it is written, or raise saying why not."""
    if response.status_code == 412:
        raise ObjectChanged(f"{url} was republished; the pinned ETag no longer matches")
    if response.status_code != PARTIAL_CONTENT:
        if response.status_code == 200:
            raise RangeNotHonored(f"{url} ignored {run.header} and offered the whole object")
        response.raise_for_status()
        raise RangeNotHonored(f"{url} answered {run.header} with HTTP {response.status_code}")
    reported = CONTENT_RANGE.fullmatch(response.headers.get("Content-Range", "").strip())
    if reported is None or (int(reported[1]), int(reported[2]), int(reported[3])) != (
        run.start,
        run.end,
        total,
    ):
        raise RangeNotHonored(
            f"{url} answered {run.header} of {total} bytes with Content-Range "
            f"{response.headers.get('Content-Range', '(absent)')!r}"
        )


def download_ranges(
    url: str,
    dest: Path,
    ranges: Sequence[ByteRange],
    *,
    etag: str,
    total: int,
    http: httpx.Client | None = None,
) -> Path:
    """Download selected byte ranges of one object and concatenate them into ``dest``.

    One GET per contiguous run, each carrying ``Range`` and ``If-Match``, with the
    runs appended in the order they were given. A response that is not 206, whose
    ``Content-Range`` disagrees with the request or the object's size, or whose
    body is the wrong length, fails the whole download before ``dest`` is touched.

    Args:
        url: The object's URL; ``s3://`` callers map it with ``s3.object_url`` first.
        dest: Path the concatenated bytes are moved to once every run has arrived.
        ranges: Ascending, non-overlapping inclusive byte ranges to fetch.
        etag: The object's ETag, bare or quoted, sent as a quoted ``If-Match`` so a
            republished object fails.
        total: The object's size, checked against every ``Content-Range``.
        http: Client to use; one is created and closed here when it is omitted.

    Returns:
        ``dest``.

    Raises:
        ValueError: The ranges are empty, out of order, overlapping, or out of bounds.
        ObjectChanged: The object was republished between listing and fetching.
        RangeNotHonored: The server answered with something other than those bytes.
    """
    runs = contiguous_runs(ranges, total)
    expected = sum(run.length for run in runs)
    own = http is None
    active = http or client()
    attempt = 0
    # An entity-tag is a quoted string (RFC 9110); records keep the bare value.
    headers = {"If-Match": '"' + etag.strip('"') + '"'}

    def request() -> Path:
        nonlocal attempt
        attempt += 1
        _progress.emit(_progress.TransferProgress(0, expected, attempt))
        completed = 0
        with staged_path(dest) as tmp, tmp.open("wb") as out:
            for run in runs:
                with active.stream(
                    "GET", url, headers={**headers, **AS_STORED, "Range": run.header}
                ) as response:
                    _honored(response, run, total, url)
                    written = 0
                    for chunk in _as_stored(response):
                        out.write(chunk)
                        written += len(chunk)
                        completed += len(chunk)
                        _progress.emit(_progress.TransferProgress(completed, expected, attempt))
                if written != run.length:
                    raise RangeNotHonored(
                        f"{url} answered {run.header} with {written} bytes, not {run.length}"
                    )
            out.flush()
        return dest

    try:
        return _retry(request)
    finally:
        if own:
            active.close()


def download(url: str, dest: Path, http: httpx.Client | None = None) -> Path:
    """Download atomically, restarting interrupted GETs up to three total attempts.

    The file holds the body as stored, never decoded from a ``Content-Encoding``
    (see ``AS_STORED``).
    """
    own = http is None
    active = http or client()
    attempt = 0

    def request() -> Path:
        nonlocal attempt
        attempt += 1
        _progress.emit(_progress.TransferProgress(0, None, attempt))
        with (
            staged_path(dest) as tmp,
            active.stream("GET", url, headers=AS_STORED) as resp,
        ):
            resp.raise_for_status()
            length = resp.headers.get("Content-Length", "")
            total = int(length) if length.isascii() and length.isdigit() else None
            completed = 0
            _progress.emit(_progress.TransferProgress(completed, total, attempt))
            with tmp.open("wb") as f:
                for chunk in _as_stored(resp):
                    f.write(chunk)
                    completed += len(chunk)
                    _progress.emit(_progress.TransferProgress(completed, total, attempt))
        return dest

    try:
        return _retry(request)
    finally:
        if own:
            active.close()
