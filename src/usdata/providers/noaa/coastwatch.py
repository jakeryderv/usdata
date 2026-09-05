"""CoastWatch SST via ERDDAP. Registered in the registry; implementation is planned for v0.1."""

from __future__ import annotations

from pathlib import Path

from usdata.models import Asset, Query
from usdata.providers.base import NotImplementedProvider, Provider


class CoastwatchSst(Provider):
    def list_assets(self, query: Query) -> list[Asset]:
        raise NotImplementedProvider(f"{self.dataset.id} adapter is not implemented yet")

    def fetch(self, asset: Asset, dest: Path) -> Path:
        raise NotImplementedProvider(f"{self.dataset.id} adapter is not implemented yet")
