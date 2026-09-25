"""The Provider interface every dataset adapter implements, and how adapters are loaded."""

from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from types import MappingProxyType, TracebackType
from typing import Any, ClassVar, Literal, Self, TypeVar

from pydantic import BaseModel, ValidationError
from pydantic_core import ErrorDetails

from usdata.models import Asset, Dataset, PartialFetch, Place, Provenance, Query, as_utc
from usdata.providers.credentials import Credentials
from usdata.query import legacy_counties

QueryField = Literal["text", "bbox", "variables", "time"]
Params = TypeVar("Params", bound=BaseModel)
_LABELS: dict[QueryField, str] = {
    "text": "text",
    "bbox": "location/bbox",
    "variables": "variables",
    "time": "start/end",
}


BARE_BOX = "bbox or lat/lon"
"""How ``Provider.place_of`` names the spatial filter a place-keyed source refuses."""


class NotImplementedProvider(NotImplementedError):
    """Raised by adapters that are registered but not yet built."""


class QueryError(ValueError):
    """The query cannot be satisfied by this dataset (missing or unsupported constraints)."""


class MissingCredentials(QueryError):
    """A source that needs credentials was about to be contacted without them.

    Raised when the adapter is built, so no request is ever sent without them.
    ``missing`` names the unset variables, and the message says where to get a key.
    """

    def __init__(self, dataset: Dataset, missing: list[str], note: str = "") -> None:
        self.dataset_id = dataset.id
        self.missing = missing
        signup = dataset.credentials.signup if dataset.credentials else None
        message = f"{dataset.id} needs {', '.join(missing)} set in the environment"
        if signup:
            message = f"{message}; request a key at {signup}"
        super().__init__(f"{message}; {note}" if note else message)


def required_credentials(dataset: Dataset, credentials: Credentials | None) -> Credentials:
    """``credentials``, checked against what ``dataset`` declares; empty for an anonymous source.

    Raises:
        MissingCredentials: A declared variable has no value in ``credentials``.
    """
    given = credentials if credentials is not None else Credentials()
    declared = [] if dataset.credentials is None else dataset.credentials.variables
    if missing := [name for name in declared if not given.get(name)]:
        raise MissingCredentials(dataset, missing)
    return given


def to_utc(value: datetime) -> datetime:
    """Apply the shared time policy: naive datetimes mean UTC, aware ones convert to it."""
    return as_utc(value)


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

    transformations: ClassVar[tuple[str, ...]] = ()
    """How ``fetch`` changes the bytes the source sent, one line each, or nothing for exact bytes.

    The core records these in every provenance sidecar the adapter's fetches
    write, beside any partial-fetch entry. Only an adapter whose source cannot be
    pinned as received declares one: a response that echoes the request's
    credentials, or differs between identical requests (ADR 0039).
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Derive ``accepted_params`` from a declared model, so one declaration feeds both."""
        super().__init_subclass__(**kwargs)
        if cls.params_model is not None:
            cls.accepted_params = described_params(cls.params_model)

    def __init__(self, dataset: Dataset, *, credentials: Credentials | None = None) -> None:
        """Bind the adapter to its registry entry, refusing to exist without declared credentials.

        Args:
            dataset: The registry entry this adapter serves.
            credentials: Values for the variables ``dataset.credentials`` declares;
                ``load_adapter`` reads them from the environment.

        Raises:
            MissingCredentials: The dataset declares a variable ``credentials`` lacks.
        """
        self.dataset = dataset
        self.credentials = required_credentials(dataset, credentials)

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

    def place_of(self, query: Query, hint: str = "") -> Place | None:
        """The state or county a query names, for a source keyed by place rather than by box.

        Such a source cannot honour a rectangle: its rows carry FIPS codes and no
        coordinates, and a box cannot be turned back into the places it covers.
        A query whose spatial filter was a ``bbox`` or a ``lat``/``lon`` is
        therefore refused, in the same words for every such source.

        Args:
            query: The query being listed.
            hint: What to do instead, usually naming the adapter's own place parameters.

        Returns:
            The place, or None when the query sets no spatial filter at all.

        Raises:
            QueryError: The query carries a box that names no place.
        """
        if query.place is None and query.bbox is not None:
            message = f"{self.dataset.id} does not support {BARE_BOX}; name a state or county"
            raise QueryError(f"{message} with location, or {hint}" if hint else message)
        return query.place

    def refuse_planning_region(self, place: Place | None) -> None:
        """Refuse a Connecticut planning region, for a source keyed by the counties before 2022.

        The place table holds both Connecticut's 2022 planning regions and the
        eight counties they replaced. A source whose rows still carry the old
        county codes has no rows under a region's code, so it would answer a
        region with nothing, or with statewide rows alone. Refusing it names the
        counties the region overlaps, which the source does know.

        Raises:
            QueryError: ``place`` is a planning region.
        """
        if place is None or not (counties := legacy_counties(place)):
            return
        names = "; ".join(county.label for county in counties)
        raise QueryError(
            f"{self.dataset.id} keys Connecticut by its eight counties before 2022, and "
            f"{place.label} is a planning region that replaced them; name a county it "
            f"overlaps with location: {names}"
        )

    def utc_window(self, query: Query) -> tuple[datetime, datetime]:
        """Both time bounds, required, in UTC. Naive bounds are read as UTC."""
        if query.time is None or query.time.start is None or query.time.end is None:
            raise QueryError(f"{self.dataset.id} requires both start and end")
        return to_utc(query.time.start), to_utc(query.time.end)

    @abstractmethod
    def list_assets(self, query: Query) -> list[Asset]:
        """Resolve a query to the concrete objects that satisfy it, without downloading."""

    def prepare_fetch(self, asset: Asset, pinned: Provenance | None = None) -> PartialFetch | None:
        """Settle how one asset will be fetched, immediately before it is written.

        The core calls this once per fetch and records whatever it returns in the
        provenance sidecar, so an adapter that fetches selected byte ranges can
        say which ones without the core knowing what they mean. It then calls
        ``fetch`` when this returns ``None`` and ``fetch_partial`` with the
        returned ranges otherwise, so neither has to look them up again.
        ``pinned`` is the provenance a lockfile holds for this asset, so a restore
        reproduces a partial fetch from the record rather than by resolving the
        query again.

        Args:
            asset: The asset about to be fetched.
            pinned: The provenance already pinned for it, when one is being restored.

        Returns:
            The byte ranges this fetch will concatenate, or ``None`` for a whole object.

        Raises:
            QueryError: The asset names a selection this adapter cannot reproduce.
        """
        return None

    @abstractmethod
    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download or materialize one whole asset to ``dest`` and return the written path."""

    def fetch_partial(self, asset: Asset, dest: Path, partial: PartialFetch) -> Path:
        """Write the byte ranges ``prepare_fetch`` settled to ``dest`` and return the written path.

        Only an adapter whose ``prepare_fetch`` can return ranges overrides this.
        Everything it needs arrives as an argument, so it depends on no earlier
        call to this adapter.

        Args:
            asset: The asset being fetched.
            dest: Path to write the concatenated ranges to.
            partial: What ``prepare_fetch`` returned for this asset.

        Raises:
            NotImplementedError: ``prepare_fetch`` returned ranges this adapter cannot fetch.
        """
        raise NotImplementedError(
            f"{type(self).__name__}.prepare_fetch returned byte ranges for {asset.id}, "
            "but the adapter does not implement fetch_partial"
        )


def adapter_class(dataset: Dataset) -> type[Provider]:
    """The Provider class a dataset's ``adapter`` dotted path names, without instantiating it.

    For what a class declares, such as ``accepted_params``, which needs no
    credentials and no transport.

    Raises:
        NotImplementedProvider: The dataset is planned and names no adapter.
    """
    if dataset.adapter is None:
        raise NotImplementedProvider(
            f"{dataset.id} is {dataset.status.value}; no adapter exists yet"
        )
    module_name, _, class_name = dataset.adapter.partition(":")
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    if not (isinstance(cls, type) and issubclass(cls, Provider)):
        raise TypeError(f"{dataset.adapter} is not a Provider subclass")
    return cls


def load_adapter(dataset: Dataset) -> Provider:
    """Instantiate the Provider named by a dataset's ``adapter`` dotted path.

    A dataset that declares credentials gets their values from the environment,
    and one that is missing any is refused here, before a request can be made.
    An anonymous dataset's adapter is built from the dataset alone, so an
    adapter that predates credentials needs no change.

    Raises:
        NotImplementedProvider: The dataset is planned and names no adapter.
        MissingCredentials: A variable the dataset declares is unset or blank.
    """
    cls = adapter_class(dataset)
    if dataset.credentials is None:
        return cls(dataset)
    return cls(dataset, credentials=Credentials.from_environment(dataset.credentials.variables))
