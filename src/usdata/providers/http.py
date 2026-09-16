"""The HTTP client lifecycle shared by adapters using an injected or owned client."""

from __future__ import annotations

import httpx

from usdata.models import Dataset
from usdata.protocols import http
from usdata.providers.base import Provider


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
    """

    def __init__(self, dataset: Dataset, client: httpx.Client | None = None) -> None:
        super().__init__(dataset)
        self._client = client
        self._owns_client = client is None

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = http.client()
        return self._client

    def close(self) -> None:
        """Close owned connections; injected clients remain the caller's responsibility."""
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None
