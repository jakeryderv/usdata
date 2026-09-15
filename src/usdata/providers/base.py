"""The Provider interface every dataset adapter implements, and how adapters are loaded."""

from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType, TracebackType
from typing import Any, ClassVar, Literal, Self, TypeVar

from pydantic import BaseModel, ValidationError
from pydantic_core import ErrorDetails

from usdata.models import Asset, Dataset, Query

QueryField = Literal["text", "bbox", "variables", "time"]
Params = TypeVar("Params", bound=BaseModel)
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


def described_params(model: type[BaseModel]) -> Mapping[str, str]:
    """Each field of a parameter model mapped to its description, as ``usdata info`` prints it."""
    described: dict[str, str] = {}
    for name, field in model.model_fields.items():
        if not field.description:
            raise ValueError(f"{model.__name__}.{name} needs a Field(description=...)")
        described[name] = field.description
    return MappingProxyType(described)


def _required_hint(model: type[BaseModel], name: str) -> str:
    """What a missing field needs, taken from the description the declaration already carries."""
    description = model.model_fields[name].description or ""
    return description.removeprefix("Required ").rstrip(".")


def _problem(detail: ErrorDetails, model: type[BaseModel]) -> str:
    """One validation failure as a line of prose, named by its field."""
    message = detail["msg"].removeprefix("Value error, ")
    if not detail["loc"]:
        return message  # A cross-field rule states its own subject.
    name = str(detail["loc"][0])
    if detail["type"] == "missing":
        return f"{name} is required: {_required_hint(model, name)}"
    return message if message.startswith(name) else f"{name} {message}"


def params_error(error: ValidationError, model: type[BaseModel]) -> QueryError:
    """Turn a parameter model's ``ValidationError`` into one ``QueryError``, a line per problem."""
    lines = dict.fromkeys(_problem(detail, model) for detail in error.errors())
    return QueryError("; ".join(lines))


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
    transport: ``parse_params`` for provider-specific keys, or ``check_params``
    for an adapter that accepts none; ``reject`` for query fields the source
    cannot honour; and ``utc_window`` for the time bounds.
    Every adapter then reports the same errors for the same mistakes, and no
    query field is silently ignored.
    """

    params_model: ClassVar[type[BaseModel] | None] = None
    """The pydantic model declaring this adapter's ``query.params``, or ``None`` for no params.

    The model is the only declaration form: ``parse_params`` validates against it
    and returns the typed parameters, and ``accepted_params`` is derived from its
    fields and their descriptions. ``None`` means the adapter takes no parameters
    at all, so it accepts no key.
    """

    accepted_params: ClassVar[Mapping[str, str]] = MappingProxyType({})
    """Accepted ``query.params`` keys, each mapped to a one-line description.

    This is the adapter's statement of what it accepts: ``list_assets`` rejects
    every key outside it, and ``usdata info`` prints it. It is always derived
    from ``params_model`` and never written by hand, so it is empty exactly when
    no model is declared; a subclass extends its parent's parameters by
    subclassing the parent's model.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Derive ``accepted_params`` from a declared model, so one declaration feeds both."""
        super().__init_subclass__(**kwargs)
        if cls.params_model is not None:
            cls.accepted_params = described_params(cls.params_model)

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
        """Reject every ``query.params`` key outside ``accepted_params``, naming it.

        An adapter that declares no ``params_model`` accepts nothing, so this is
        its whole parameter check; ``parse_params`` runs it first for the rest.
        """
        if unknown := set(query.params) - set(self.accepted_params):
            raise QueryError(f"unsupported {self.dataset.id} params: {', '.join(sorted(unknown))}")

    def parse_params(self, query: Query, model: type[Params]) -> Params:
        """Validate ``query.params`` against ``model`` and return the typed parameters.

        Unknown keys are named first, on their own, so a typo reads the same
        whatever else the query got wrong; the remaining problems are reported
        together, one line each.
        """
        self.check_params(query)
        try:
            return model.model_validate(query.params)
        except ValidationError as error:
            raise params_error(error, model) from None

    def validate_params(self, query: Query) -> None:
        """Check ``query.params`` as far as this adapter declares them, without any transport.

        The core calls this before fetching anything, so a bad source fails
        before its siblings download.
        """
        if self.params_model is None:
            self.check_params(query)
        else:
            self.parse_params(query, self.params_model)

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
