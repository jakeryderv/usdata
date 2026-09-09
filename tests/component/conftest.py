import importlib
from pathlib import Path

import pytest

from usdata.models import Asset, Dataset, Protocol, Query, Status
from usdata.providers.base import Provider


@pytest.fixture
def fake_source(monkeypatch):
    """Exercise core invariants without tying them to an upstream adapter."""
    dataset = Dataset(
        id="test:bytes",
        provider="test",
        title="Test bytes",
        protocol=Protocol.HTTP,
        domain="test",
        status=Status.AVAILABLE,
        since="0.1",
        adapter="test:FakeProvider",
    )
    state = {"fetches": 0, "closed": 0}

    class FakeProvider(Provider):
        def list_assets(self, query: Query) -> list[Asset]:
            return [
                Asset(
                    id="data",
                    dataset_id=dataset.id,
                    href="https://example.test/bytes",
                    protocol=Protocol.HTTP,
                )
            ]

        def fetch(self, asset: Asset, dest: Path) -> Path:
            state["fetches"] += 1
            dest.write_bytes(b"original")
            return dest

        def close(self) -> None:
            state["closed"] += 1

    monkeypatch.setattr(importlib.import_module("usdata.fetch"), "load_adapter", FakeProvider)
    return dataset, state
