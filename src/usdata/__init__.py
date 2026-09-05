"""usdata: unified access and provenance for U.S. public scientific data."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

try:
    __version__ = version("usdata")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0"

from usdata.models import Asset, BBox, Dataset, Provenance, Query, TimeRange
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import DatasetNotFound, Registry, SearchResult, default_registry

__all__ = [
    "Asset",
    "BBox",
    "Dataset",
    "DatasetNotFound",
    "Provenance",
    "Query",
    "Registry",
    "SearchResult",
    "TimeRange",
    "__version__",
    "build_query",
    "default_registry",
    "get",
    "pull",
    "search",
    "verify",
]


def search(
    text: str | None = None, *, include_planned: bool = False, **kwargs: Any
) -> list[SearchResult]:
    """Search the curated registry. Keyword arguments match ``build_query``."""
    return default_registry().search(build_query(text, **kwargs), include_planned=include_planned)


def get(dataset_id: str) -> Dataset:
    """Look up a dataset by ``provider:name`` id."""
    return default_registry().get(dataset_id)
