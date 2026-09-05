"""NEXRAD Level II via NODD S3. Registered in the registry; implementation is planned for v0.1."""

from __future__ import annotations

from pathlib import Path

from usdata.models import Asset, Query
from usdata.providers.base import NotImplementedProvider, Provider


class NexradLevel2(Provider):
    def list_assets(self, query: Query) -> list[Asset]:
        raise NotImplementedProvider(f"{self.dataset.id} adapter is not implemented yet")

    def fetch(self, asset: Asset, dest: Path) -> Path:
        raise NotImplementedProvider(f"{self.dataset.id} adapter is not implemented yet")
