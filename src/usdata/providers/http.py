"""The HTTP client lifecycle shared by adapters using an injected or owned client."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import httpx

from usdata.models import Dataset
from usdata.protocols import http
from usdata.providers.base import Provider
from usdata.providers.credentials import Credentials

HTTPX_LOGGER = "httpx"
"""The logger httpx writes each request line to, URL and query string included."""


class _RedactingFilter(logging.Filter):
    """Rewrite a log record so no credential value survives formatting."""

    def __init__(self, credentials: Credentials) -> None:
        super().__init__()
        self._credentials = credentials

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = self._credentials.redact(message)
        if redacted != message:
            record.msg, record.args = redacted, None
        return True


def _redacted_url(url: httpx.URL, credentials: Credentials) -> httpx.URL:
    return httpx.URL(credentials.redact(str(url)))


def _redact_error(error: BaseException, credentials: Credentials) -> None:
    """Remove credential values from ``error`` and every exception chained to it, in place.

    String arguments are redacted, and an httpx error's request and response are
    replaced by copies with a redacted URL and no body: an error body can echo
    the request, as the AQS header does. Rewriting in place keeps the exception's
    type and traceback, and raising it again adds no chained original that
    still holds the key.
    """
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        current.args = tuple(
            credentials.redact(arg) if isinstance(arg, str) else arg for arg in current.args
        )
        if isinstance(current, httpx.HTTPError):
            try:
                original = current.request
            except RuntimeError:  # An error raised without a request has none to redact.
                original = None
            if original is not None:
                request = httpx.Request(original.method, _redacted_url(original.url, credentials))
                current.request = request
                if isinstance(current, httpx.HTTPStatusError):
                    current.response = httpx.Response(current.response.status_code, request=request)
        current = current.__cause__ or current.__context__


class HttpProvider(Provider):
    """A ``Provider`` that reaches its source over HTTP, with one client per adapter.

    Adapters inherit this rather than repeating the lifecycle: the client is
    created on first use, an injected one is used as given and stays the
    caller's to close, and an owned one is closed when the adapter is. It holds
    no query, pagination, or dataset knowledge, so the ``Provider`` interface
    itself remains transport-independent.

    Subclasses reach the client through ``self._http()`` and pass it to the
    helpers in ``usdata.protocols``::

        class StormEvents(HttpProvider):
            def list_assets(self, query: Query) -> list[Asset]:
                page = http.get(DIRECTORY_URL, self._http()).text
                ...

    An adapter whose dataset declares credentials adds them to each request as
    it sends it, inside ``redacted_errors``, so a failed request cannot carry a
    key out in its message. While such an adapter holds a client, httpx's
    request log lines are redacted too.
    """

    def __init__(
        self,
        dataset: Dataset,
        client: httpx.Client | None = None,
        *,
        credentials: Credentials | None = None,
    ) -> None:
        super().__init__(dataset, credentials=credentials)
        self._client = client
        self._owns_client = client is None
        self._log_filter: _RedactingFilter | None = None

    def _http(self) -> httpx.Client:
        if self.credentials and self._log_filter is None:
            self._log_filter = _RedactingFilter(self.credentials)
            logging.getLogger(HTTPX_LOGGER).addFilter(self._log_filter)
        if self._client is None:
            self._client = http.client()
        return self._client

    @contextmanager
    def redacted_errors(self) -> Iterator[None]:
        """Let any exception out only after removing this adapter's credential values from it.

        Wrap every request that carries credentials::

            with self.redacted_errors():
                response = http.get(url, self._http(), params={"key": self.credentials[KEY]})

        The exception is rewritten in place and re-raised, so its type, and any
        handling a caller has for it, are unchanged.
        """
        try:
            yield
        except BaseException as error:
            _redact_error(error, self.credentials)
            raise

    def close(self) -> None:
        """Close owned connections; injected clients remain the caller's responsibility."""
        if self._log_filter is not None:
            logging.getLogger(HTTPX_LOGGER).removeFilter(self._log_filter)
            self._log_filter = None
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None
