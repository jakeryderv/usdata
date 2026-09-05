"""Curated dataset registry bundled with the package.

v0.1 search runs over this registry, not over live agency catalogs. See
docs/adr/0001-curated-registry-over-federated-search.md.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from functools import lru_cache
from importlib import resources
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from usdata.models import Dataset, ProviderInfo, Query

_TOKEN = re.compile(r"[a-z0-9]+")


class DatasetNotFound(KeyError):
    """No registry entry has the requested id."""

    pass


class SearchResult(BaseModel):
    """A dataset and its keyword-match score."""

    model_config = ConfigDict(frozen=True)

    dataset: Dataset
    score: float


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def _score(dataset: Dataset, terms: set[str]) -> float:
    if not terms:
        return 1.0
    id_t = _tokens(dataset.id)
    title_t = _tokens(dataset.title)
    kw_t = _tokens(" ".join(dataset.keywords))
    desc_t = _tokens(dataset.description)
    score = 0.0
    for term in terms:
        if term in id_t:
            score += 3
        if term in title_t:
            score += 2
        if term in kw_t:
            score += 2
        if term in desc_t:
            score += 1
    return score


class Registry:
    """An in-memory collection of datasets addressable by id and searchable by keyword."""

    def __init__(self, datasets: Iterable[Dataset], providers: Iterable[ProviderInfo] = ()) -> None:
        self._by_id: dict[str, Dataset] = {}
        for ds in datasets:
            if ds.id in self._by_id:
                raise ValueError(f"duplicate dataset id {ds.id!r}")
            self._by_id[ds.id] = ds
        self._providers = {p.id: p for p in providers}
        for ds in self._by_id.values():
            self._providers.setdefault(
                ds.provider, ProviderInfo(id=ds.provider, name=ds.provider.upper())
            )

    @classmethod
    def from_yaml(cls, path: Path) -> Registry:
        """Load a registry from YAML with top-level ``providers`` and ``datasets``."""
        raw = yaml.safe_load(path.read_text()) or {}
        providers = [
            ProviderInfo(id=pid, **(info or {})) for pid, info in raw.get("providers", {}).items()
        ]
        return cls((Dataset.model_validate(d) for d in raw.get("datasets", [])), providers)

    @classmethod
    def bundled(cls) -> Registry:
        """The registry shipped inside the package."""
        with resources.as_file(resources.files("usdata.data") / "registry.yaml") as p:
            return cls.from_yaml(p)

    def __iter__(self) -> Iterator[Dataset]:
        return iter(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, dataset_id: object) -> bool:
        return dataset_id in self._by_id

    def get(self, dataset_id: str) -> Dataset:
        """Return the dataset with this id or raise DatasetNotFound."""
        try:
            return self._by_id[dataset_id]
        except KeyError:
            raise DatasetNotFound(dataset_id) from None

    def providers(self) -> set[str]:
        """The set of provider ids present in the registry."""
        return {ds.provider for ds in self}

    def provider(self, provider_id: str) -> ProviderInfo:
        """Display information for a provider id."""
        return self._providers[provider_id]

    def search(self, query: Query) -> list[SearchResult]:
        """Rank datasets by keyword match, filtered by provider, space, and time."""
        terms = _tokens(query.text or "")
        results: list[SearchResult] = []
        for ds in self:
            if query.provider and ds.provider != query.provider:
                continue
            if query.bbox and ds.spatial_extent and not ds.spatial_extent.intersects(query.bbox):
                continue
            if query.time and ds.temporal_extent and not ds.temporal_extent.overlaps(query.time):
                continue
            score = _score(ds, terms)
            if score > 0:
                results.append(SearchResult(dataset=ds, score=score))
        results.sort(key=lambda r: (-r.score, r.dataset.id))
        return results


@lru_cache(maxsize=1)
def default_registry() -> Registry:
    """The bundled registry, loaded once per process."""
    return Registry.bundled()
