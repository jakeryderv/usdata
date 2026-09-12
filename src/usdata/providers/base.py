"""The Provider interface every dataset adapter implements, and how adapters are loaded."""

from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType, TracebackType
from typing import ClassVar, Literal, Self

from usdata.models import Asset, Dataset, Query

QueryField = Literal["text", "bbox", "variables", "time"]
_LABELS: dict[QueryField, str] = {
    "text": "text",
    "bbox": "location/bbox",
    "variables": "variables",
    "time": "start/end",
}


class NotImplementedProvider(NotImplementedError):
    """Raised by adapters that are registered but not yet built."""


class QueryError(ValueError):
    """The query cannot be satisfied by this dataset (missing or unsupported constraints)."""


def to_utc(value: datetime) -> datetime:
    """Apply the shared time policy: naive datetimes mean UTC, aware ones convert to it."""
    return value.replace(tzinfo=value.tzinfo or UTC).astimezone(UTC)


def _is_set(query: Query, field: QueryField) -> bool:
    if field == "text":
        return bool(query.text)
    if field == "bbox":
        return query.bbox is not None
    if field == "variables":
        return bool(query.variables)
    return query.time is not None


class Provider(ABC):
    """One adapter per dataset. Translates a normalized query into concrete assets.

    ``list_assets`` implementations validate with the shared helpers before any
    transport: ``check_params`` for provider-specific keys, ``reject`` for query
    fields the source cannot honour, and ``utc_window`` for the time bounds.
    Every adapter then reports the same errors for the same mistakes, and no
    query field is silently ignored.
    """

    accepted_params: ClassVar[Mapping[str, str]] = MappingProxyType({})
    """Accepted ``query.params`` keys, each mapped to a one-line description.

    This is the adapter's statement of what it accepts: ``list_assets`` rejects
    every key outside it, and ``usdata info`` prints it. Subclasses that extend a
    parent's set spread it, as ``{**Parent.accepted_params, "extra": "..."}``.
    """

    def __init__(self, dataset: Dataset) -> None:
        self.dataset = dataset

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Release owned resources. Providers with resources override this method."""
        return None

    def check_params(self, query: Query) -> None:
        """Reject every ``query.params`` key outside ``accepted_params``, naming it."""
        if unknown := set(query.params) - set(self.accepted_params):
            raise QueryError(f"unsupported {self.dataset.id} params: {', '.join(sorted(unknown))}")

    def reject(self, query: Query, *fields: QueryField, hint: str = "") -> None:
        """Raise ``QueryError`` when the query sets a field this dataset cannot honour.

        Sources that ignore a filter must say so rather than return unfiltered
        data; ``hint`` tells the caller what to do instead.
        """
        present = [_LABELS[field] for field in fields if _is_set(query, field)]
        if present:
            message = f"{self.dataset.id} does not support {', '.join(present)}"
            raise QueryError(f"{message}; {hint}" if hint else message)

    def utc_window(self, query: Query) -> tuple[datetime, datetime]:
        """Both time bounds, required, in UTC. Naive bounds are read as UTC."""
        if query.time is None or query.time.start is None or query.time.end is None:
            raise QueryError(f"{self.dataset.id} requires both start and end")
        return to_utc(query.time.start), to_utc(query.time.end)

    @abstractmethod
    def list_assets(self, query: Query) -> list[Asset]:
        """Resolve a query to the concrete objects that satisfy it, without downloading."""

    @abstractmethod
    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download or materialize one asset to ``dest`` and return the written path."""


def load_adapter(dataset: Dataset) -> Provider:
    """Instantiate the Provider named by a dataset's ``adapter`` dotted path."""
    if dataset.adapter is None:
        raise NotImplementedProvider(
            f"{dataset.id} is {dataset.status.value}; no adapter exists yet"
        )
    module_name, _, class_name = dataset.adapter.partition(":")
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    if not (isinstance(cls, type) and issubclass(cls, Provider)):
        raise TypeError(f"{dataset.adapter} is not a Provider subclass")
    return cls(dataset)
