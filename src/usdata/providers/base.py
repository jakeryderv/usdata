from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from pathlib import Path

from usdata.models import Asset, Dataset, Query


class NotImplementedProvider(NotImplementedError):
    """Raised by adapters that are registered but not yet built."""


class Provider(ABC):
    """One adapter per dataset. Translates a normalized query into concrete assets."""

    def __init__(self, dataset: Dataset) -> None:
        self.dataset = dataset

    @abstractmethod
    def list_assets(self, query: Query) -> list[Asset]:
        """Resolve a query to the concrete objects that satisfy it, without downloading."""

    @abstractmethod
    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download or materialize one asset to ``dest`` and return the written path."""


def load_adapter(dataset: Dataset) -> Provider:
    module_name, _, class_name = dataset.adapter.partition(":")
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    if not (isinstance(cls, type) and issubclass(cls, Provider)):
        raise TypeError(f"{dataset.adapter} is not a Provider subclass")
    return cls(dataset)
