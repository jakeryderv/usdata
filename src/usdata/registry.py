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

from usdata.models import (
    LATER,
    Capabilities,
    Dataset,
    DomainInfo,
    ProviderInfo,
    Query,
    Status,
    SystemInfo,
)

_TOKEN = re.compile(r"[a-z0-9]+")

CAPABILITY_NAMES = tuple(Capabilities.model_fields)
"""Server-side capability names a listing may filter on."""

STATUS_FILTERS = (*(s.value for s in Status), "all")
"""Accepted values of the ``status`` listing filter."""

NO_READER = "none"
"""The ``reader`` filter value that selects datasets delivering bytes only."""


def version_key(version: str) -> tuple[int, ...]:
    """Sort key placing numeric versions in order and 'later' after all of them."""
    if version == LATER:
        return (10**6,)
    return tuple(int(part) for part in version.split("."))


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

    def __init__(
        self,
        datasets: Iterable[Dataset],
        providers: Iterable[ProviderInfo] = (),
        domains: Iterable[DomainInfo] = (),
        systems: Iterable[SystemInfo] = (),
    ) -> None:
        self._by_id: dict[str, Dataset] = {}
        for ds in datasets:
            if ds.id in self._by_id:
                raise ValueError(f"duplicate dataset id {ds.id!r}")
            self._by_id[ds.id] = ds
        self._providers = {p.id: p for p in providers}
        self._domains = {d.id: d for d in domains}
        self._systems = {s.id: s for s in systems}
        explicit_domains = bool(self._domains)
        explicit_systems = bool(self._systems)
        for ds in self._by_id.values():
            self._providers.setdefault(
                ds.provider, ProviderInfo(id=ds.provider, name=ds.provider.upper())
            )
            if explicit_domains and ds.domain not in self._domains:
                raise ValueError(f"{ds.id}: unknown domain {ds.domain!r}")
            self._domains.setdefault(ds.domain, DomainInfo(id=ds.domain, name=ds.domain))
            if ds.system is not None:
                self._check_system(ds, ds.system, explicit_systems)

    def _check_system(self, ds: Dataset, system_id: str, explicit: bool) -> None:
        """A named system is declared, or inferred, and publishes for this entry's provider."""
        if explicit and system_id not in self._systems:
            raise ValueError(f"{ds.id}: unknown system {system_id!r}")
        system = self._systems.setdefault(
            system_id, SystemInfo(id=system_id, name=system_id, provider=ds.provider)
        )
        if system.provider != ds.provider:
            raise ValueError(
                f"{ds.id}: system {system_id!r} belongs to provider {system.provider!r}"
            )

    @classmethod
    def from_yaml(cls, path: Path) -> Registry:
        """Load from YAML with ``providers``, ``domains``, ``systems``, and ``datasets``."""
        raw = yaml.safe_load(path.read_text()) or {}
        if "catalog" in raw:
            raise ValueError(
                f"{path}: the top-level 'catalog' block is gone; guide, summary, formats, "
                "selection, inputs, reader (was reader_extra), and examples now belong on "
                "each entry under 'datasets'"
            )
        providers = [
            ProviderInfo(id=pid, **(info or {})) for pid, info in raw.get("providers", {}).items()
        ]
        domains = [
            DomainInfo(id=did, **(info or {})) for did, info in raw.get("domains", {}).items()
        ]
        systems = [
            SystemInfo(id=sid, **(info or {})) for sid, info in raw.get("systems", {}).items()
        ]
        datasets = (Dataset.model_validate(d) for d in raw.get("datasets", []))
        return cls(datasets, providers, domains, systems)

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

    def domain(self, domain_id: str) -> DomainInfo:
        """Display information for a domain id."""
        return self._domains[domain_id]

    def domains(self) -> list[DomainInfo]:
        """All declared domains in declaration order."""
        return list(self._domains.values())

    def system(self, system_id: str) -> SystemInfo:
        """Display information for a system id."""
        return self._systems[system_id]

    def systems(self, provider: str | None = None) -> list[SystemInfo]:
        """All declared systems in declaration order, optionally for one provider."""
        return [s for s in self._systems.values() if provider is None or s.provider == provider]

    def next_target(self) -> str | None:
        """The nearest version any planned dataset is aimed at, or None."""
        targets = {ds.target for ds in self if ds.target and ds.target != LATER}
        return min(targets, key=version_key) if targets else None

    def list(
        self,
        *,
        provider: str | None = None,
        domain: str | None = None,
        format: str | None = None,
        reader: str | None = None,
        capability: str | None = None,
        status: str = "available",
    ) -> list[Dataset]:
        """Datasets matching every filter given, in registry order.

        ``provider`` and ``domain`` match an id exactly. ``format`` matches
        case-insensitively anywhere in a declared format, so ``csv`` also finds
        ``gzip CSV``. ``reader`` names the extra that opens the files, or
        ``'none'`` for datasets delivering bytes only. ``capability`` names one
        of ``CAPABILITY_NAMES`` and keeps datasets declaring it true.
        ``status`` is ``'available'``, ``'planned'``, or ``'all'``.
        """
        if capability is not None and capability not in CAPABILITY_NAMES:
            raise ValueError(
                f"unknown capability {capability!r}; choose one of {', '.join(CAPABILITY_NAMES)}"
            )
        if status not in STATUS_FILTERS:
            raise ValueError(
                f"unknown status {status!r}; choose one of {', '.join(STATUS_FILTERS)}"
            )
        wanted_format = format.casefold() if format is not None else None
        matches: list[Dataset] = []
        for ds in self:
            if status != "all" and ds.status.value != status:
                continue
            if provider is not None and ds.provider != provider:
                continue
            if domain is not None and ds.domain != domain:
                continue
            if wanted_format is not None and not any(
                wanted_format in declared.casefold() for declared in ds.formats
            ):
                continue
            if reader is not None and (ds.reader or NO_READER) != reader:
                continue
            if capability is not None and not ds.capabilities.model_dump()[capability]:
                continue
            matches.append(ds)
        return matches

    def search(
        self,
        query: Query,
        *,
        include_planned: bool = False,
        provider: str | None = None,
        domain: str | None = None,
        format: str | None = None,
        reader: str | None = None,
        capability: str | None = None,
        status: str | None = None,
    ) -> list[SearchResult]:
        """Rank datasets by keyword match, filtered by provider, space, and time.

        The keyword arguments are the ``list`` filters, applied before scoring.
        Planned datasets are left out unless ``include_planned`` is set;
        ``status`` supersedes it when given.
        """
        terms = _tokens(query.text or "")
        results: list[SearchResult] = []
        candidates = self.list(
            provider=provider,
            domain=domain,
            format=format,
            reader=reader,
            capability=capability,
            status=status if status is not None else "all" if include_planned else "available",
        )
        for ds in candidates:
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
