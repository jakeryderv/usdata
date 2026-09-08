"""Shared HTTP configuration and bounded retries for idempotent GET requests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import sleep
from typing import Any, TypeVar

import httpx

from usdata import __version__, _progress
from usdata._files import staged_path

USER_AGENT = f"usdata/{__version__} (+https://github.com/jakeryderv/usdata)"
DEFAULT_TIMEOUT = httpx.Timeout(10.0, read=120.0)
MAX_ATTEMPTS = 3
MAX_RETRY_DELAY = 30.0
RETRY_STATUS = {429, 500, 502, 503, 504}
T = TypeVar("T")


def client(**kwargs: Any) -> httpx.Client:
    """A configured client. Callers own its lifetime; use as a context manager."""
    kwargs.setdefault("headers", {"User-Agent": USER_AGENT})
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    kwargs.setdefault("follow_redirects", True)
    return httpx.Client(**kwargs)


def _retry_after(response: httpx.Response) -> float:
    value = response.headers.get("Retry-After", "")
    if value.isdigit():
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


def get(url: str | httpx.URL, http: httpx.Client, **kwargs: Any) -> httpx.Response:
    """GET a metadata page with bounded retries; the caller owns the client."""

    def request() -> httpx.Response:
        response = http.get(url, **kwargs)
        response.raise_for_status()
        return response

    return _retry(request)


def download(url: str, dest: Path, http: httpx.Client | None = None) -> Path:
    """Download atomically, restarting interrupted GETs up to three total attempts."""
    own = http is None
    active = http or client()
    attempt = 0

    def request() -> Path:
        nonlocal attempt
        attempt += 1
        _progress.emit(_progress.TransferProgress(0, None, attempt))
        with staged_path(dest) as tmp, active.stream("GET", url) as resp:
            resp.raise_for_status()
            length = resp.headers.get("Content-Length", "")
            # iter_bytes writes decoded bytes; an encoded length is not comparable.
            total = (
                int(length)
                if length.isascii()
                and length.isdigit()
                and resp.headers.get("Content-Encoding", "identity").lower() == "identity"
                else None
            )
            completed = 0
            _progress.emit(_progress.TransferProgress(completed, total, attempt))
            with tmp.open("wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
                    completed += len(chunk)
                    _progress.emit(_progress.TransferProgress(completed, total, attempt))
        return dest

    try:
        return _retry(request)
    finally:
        if own:
            active.close()
