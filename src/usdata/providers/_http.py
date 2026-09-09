"""Internal lifecycle shared by adapters using an injected or owned HTTP client."""

from __future__ import annotations

import httpx

from usdata.models import Dataset
from usdata.protocols import http
from usdata.providers.base import Provider


class _HttpProvider(Provider):
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
