"""The adapter contract as runnable checks, for adapters inside this repository and outside it.

``usdata`` holds every adapter it ships to the same behavioral rules: an adapter
lists assets without downloading them, refuses the query fields its source
cannot honour before allocating any transport, fetches exactly the bytes it was
asked for to exactly the path it was given, and closes only the client it owns.
This module is the one implementation of those rules, so an adapter distributed
elsewhere can run the same checks that ``tests/adapters/test_contracts.py`` runs
over the bundled ones.

A caller supplies three things: the ``Dataset`` entry the adapter serves, a
factory that builds the adapter (with no argument for an adapter that owns its
client, and with ``client=`` for one that borrows a caller's), and a query the
adapter should resolve to exactly one asset. Transport stays the caller's: a
``client_factory`` returns an ``httpx.Client`` wired to a mock transport, and
the checks install it as ``usdata.protocols.http.client`` for their duration::

    from usdata.testing import check_provider_contract

    def test_my_adapter(tmp_path):
        check_provider_contract(
            MY_DATASET,
            lambda client=None: MyProvider(MY_DATASET, client),
            build_query(start=..., end=..., sites="07164500"),
            client_factory=lambda: httpx.Client(transport=my_mock_transport()),
            expected_bytes=DATA,
            arm_download=downloads.add,
            work_dir=tmp_path,
        )

Every check reports a failure as an ordinary assertion, so it reads the same
under pytest as a test written by hand. ``pytest`` itself is imported inside the
checks that need it rather than at module scope, so it stays a development
dependency of ``usdata`` and importing this module never requires it at runtime.
"""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager, nullcontext
from datetime import timedelta, timezone
from pathlib import Path

import httpx

from usdata.models import BBox, Dataset, Query, TimeRange
from usdata.protocols import http, s3
from usdata.providers import Provider, QueryError
from usdata.providers.base import QueryField

AdapterFactory = Callable[..., Provider]
"""Builds the adapter: no argument for an owned client, ``client=`` for an injected one."""

ClientFactory = Callable[..., httpx.Client]
"""Builds one ``httpx.Client`` on a mock transport, standing in for ``protocols.http.client``."""

PROBE_BBOX = BBox(west=-97.7, south=35.2, east=-97.2, north=35.7)
"""The bounding box the capability probes ask for, small enough to name one place."""

REFUSED: dict[QueryField, str] = {
    "bbox": "location/bbox",
    "variables": "variables",
    "time": "start/end",
}
"""How ``Provider.reject`` names each field it refuses, which is what a refusal is read from."""

SELECTORS = frozenset({"site", "sites", "station", "stations", "nearest"})
"""Parameters naming a station or site. A bbox stands in for one wherever they are declared."""

PARTIAL_PARAM = "messages"
"""The parameter an adapter declaring ``partial_fetch`` asks for a byte subset through."""


class TransportReached(Exception):
    """Raised in place of a client, so a probe that got past validation is visible."""


@contextmanager
def _patched_client(factory: ClientFactory) -> Iterator[None]:
    """Answer every ``protocols.http.client()`` call with ``factory`` for the duration."""
    original = http.client
    http.client = factory
    try:
        yield
    finally:
        http.client = original


@contextmanager
def _isolated_cache(root: Path) -> Iterator[None]:
    """Point the cache at a path under ``root``, so a provider that writes one is visible."""
    previous = os.environ.get("USDATA_CACHE_DIR")
    os.environ["USDATA_CACHE_DIR"] = str(root / "forbidden-cache")
    try:
        yield
    finally:
        if previous is None:
            del os.environ["USDATA_CACHE_DIR"]
        else:
            os.environ["USDATA_CACHE_DIR"] = previous


@contextmanager
def _work_dir(given: Path | None) -> Iterator[Path]:
    """One empty directory for one fetch: a fresh one under the caller's, or a temporary one."""
    if given is None:
        with tempfile.TemporaryDirectory() as name:
            yield Path(name)
        return
    yield Path(tempfile.mkdtemp(dir=given))


def _raises(expected: type[BaseException]) -> AbstractContextManager[object]:
    """``pytest.raises``, with pytest imported only when a check runs."""
    import pytest

    return pytest.raises(expected)


def _refusal(adapter: Provider, query: Query) -> str:
    """The ``QueryError`` message ``list_assets`` raises for ``query``, which it must."""
    import pytest

    with pytest.raises(QueryError) as caught:
        adapter.list_assets(query)
    return str(caught.value)


def _download_url(href: str) -> str:
    """The HTTPS URL an ``href`` is fetched from, as the transport sees it."""
    target = s3.https_url(*s3.parse_s3_url(href)) if href.startswith("s3://") else href
    return str(httpx.URL(target))


def _refuses(adapter: Provider, probe: Query, field: QueryField) -> bool:
    """Whether ``adapter`` refuses ``field`` outright, before reaching any transport.

    Only ``Provider.reject`` counts: its wording is the adapter's statement that
    the source cannot honour the field at all, as opposed to a rule about how
    one query combines its inputs.
    """
    try:
        adapter.list_assets(probe)
    except QueryError as error:
        message = str(error)
        return message.startswith(f"{adapter.dataset.id} does not support") and (
            REFUSED[field] in message
        )
    except TransportReached:
        return False
    return False


def _demands_window(adapter: Provider, probe: Query) -> bool:
    """Whether ``adapter`` refuses a query that leaves start and end out."""
    try:
        adapter.list_assets(probe)
    except QueryError as error:
        return str(error) == f"{adapter.dataset.id} requires both start and end"
    except TransportReached:
        return False
    return False


def check_params_declaration(adapter_factory: AdapterFactory) -> None:
    """The model is the only declaration form, and no model means no accepted parameter.

    An adapter either declares a model that forbids extras and fills
    ``accepted_params``, or declares none and accepts nothing at all.
    """
    with adapter_factory() as adapter:
        dataset_id = adapter.dataset.id
        model = adapter.params_model
        if model is None:
            assert dict(adapter.accepted_params) == {}, dataset_id
            return
        assert model.model_config.get("extra") == "forbid", dataset_id
        assert set(adapter.accepted_params) == set(model.model_fields), dataset_id


def check_declared_params(adapter_factory: AdapterFactory, scenario_query: Query) -> None:
    """Every declared key is accepted; a key outside the declaration is named as unsupported.

    This probes one undeclared key, so it catches an adapter that narrowed its
    check below the declaration, not one that quietly widened it to keys nobody
    declared. Only reading ``accepted_params`` in the rejection gives that.
    """

    def unexpected_client() -> httpx.Client:
        raise AssertionError("parameter validation must precede any transport")

    with _patched_client(unexpected_client), adapter_factory() as adapter:
        declared = dict(adapter.accepted_params)
        assert all(
            description.strip() and "\n" not in description for description in declared.values()
        )
        probe = scenario_query.model_copy(
            update={"params": {**dict.fromkeys(declared, "probe"), "unknown-key": "probe"}}
        )
        message = _refusal(adapter, probe)
    reported = re.search(r"unsupported .*params: (.+)$", message)
    assert reported is not None, f"{adapter.dataset.id} rejected a declared parameter: {message}"
    assert reported[1] == "unknown-key"


def check_text_refused(adapter_factory: AdapterFactory, scenario_query: Query) -> None:
    """Free text searches the registry; no adapter can honour it, so none may ignore it."""

    def unexpected_client() -> httpx.Client:
        raise AssertionError("an unsupported query field must fail before any transport")

    probe = scenario_query.model_copy(update={"text": "precipitation"})
    with _patched_client(unexpected_client), adapter_factory() as adapter, _raises(QueryError):
        adapter.list_assets(probe)


def check_invalid_params_refused(adapter_factory: AdapterFactory, scenario_query: Query) -> None:
    """An unknown parameter is rejected before any client is allocated."""

    def unexpected_client() -> httpx.Client:
        raise AssertionError("invalid query must fail before allocating a client")

    invalid = scenario_query.model_copy(update={"params": {**scenario_query.params, "typo": 1}})
    with _patched_client(unexpected_client), adapter_factory() as adapter, _raises(QueryError):
        adapter.list_assets(invalid)


def check_utc_equivalence(
    adapter_factory: AdapterFactory, scenario_query: Query, client_factory: ClientFactory
) -> None:
    """Naive bounds mean UTC and aware ones convert, whatever the adapter's own time logic."""
    aware = scenario_query
    assert aware.time and aware.time.start and aware.time.end
    naive = aware.model_copy(
        update={
            "time": TimeRange(
                start=aware.time.start.replace(tzinfo=None),
                end=aware.time.end.replace(tzinfo=None),
            )
        }
    )
    eastern = timezone(timedelta(hours=-5))
    shifted = aware.model_copy(
        update={
            "time": TimeRange(
                start=aware.time.start.astimezone(eastern), end=aware.time.end.astimezone(eastern)
            )
        }
    )
    with _patched_client(client_factory), adapter_factory() as adapter:
        expected = adapter.list_assets(aware)
        assert len(expected) == 1
        assert adapter.list_assets(naive) == expected
        assert adapter.list_assets(shifted) == expected
    assert all(a.time and a.time.start and a.time.start.utcoffset() is not None for a in expected)


def check_declared_capabilities(
    dataset: Dataset,
    adapter_factory: AdapterFactory,
    scenario_query: Query,
    timed_query: Query,
) -> None:
    """A declared capability is one the adapter accepts, and a false one is a field it refuses.

    The probes stop at validation: the transport raises instead of connecting,
    and reaching it counts as acceptance. A refusal is read from
    ``Provider.reject``, so a rule such as GHCN's "pass stations or a
    location/bbox, not both" is not one; it constrains how a query combines its
    inputs rather than what the source can do.

    A bbox means two things. For a gridded or whole-file source it asks for a
    spatial subset, and the adapter either honours it or refuses it. For a
    source that selects by station or site -- one whose parameters name them --
    a bbox only chooses which stations or sites to ask for, and each asset still
    arrives whole, so accepting one proves nothing about subsetting. Those
    adapters are held to the refusal direction alone: refusing a bbox still
    means ``spatial_subset`` is false, while accepting one may be either.

    ``temporal_subset`` is false only where the window plays no part, which
    HURDAT2 shows by refusing start/end. Such a dataset must not require a
    window either, having nothing to select with it.

    ``partial_fetch`` is the claim that a caller can ask for part of an object
    and get a file of the declared media type back, so it is read from the
    adapter's declared parameters: an adapter that promises it declares
    ``messages``, and one that does not must not, since there would be no way
    to ask.
    """
    dataset_id = dataset.id

    def unexpected_client() -> httpx.Client:
        raise TransportReached(dataset_id)

    declared = dataset.capabilities
    assert dataset.variables, f"{dataset_id} names no variable to probe with"
    variable = dataset.variables[0].name
    with _patched_client(unexpected_client), adapter_factory() as adapter:
        base = scenario_query
        bbox_refused = _refuses(adapter, base.model_copy(update={"bbox": PROBE_BBOX}), "bbox")
        variables_refused = _refuses(
            adapter, base.model_copy(update={"variables": [variable]}), "variables"
        )
        time_refused = _refuses(adapter, timed_query, "time")
        requires_window = _demands_window(adapter, base.model_copy(update={"time": None}))
        selects_by_site = bool(SELECTORS & set(adapter.accepted_params))
        selects_parts = PARTIAL_PARAM in adapter.accepted_params

    assert variables_refused is not declared.variable_subset, (
        f"{dataset_id} declares variable_subset={declared.variable_subset} and "
        f"{'refuses' if variables_refused else 'accepts'} variables={variable!r}"
    )
    assert time_refused is not declared.temporal_subset, (
        f"{dataset_id} declares temporal_subset={declared.temporal_subset} and "
        f"{'refuses' if time_refused else 'accepts'} a query window"
    )
    if not declared.temporal_subset:
        assert not requires_window, f"{dataset_id} requires a window it declares it cannot use"
    assert selects_parts is declared.partial_fetch, (
        f"{dataset_id} declares partial_fetch={declared.partial_fetch} and "
        f"{'declares' if selects_parts else 'declares no'} {PARTIAL_PARAM!r} parameter"
    )
    if bbox_refused:
        assert not declared.spatial_subset, f"{dataset_id} declares a bbox its adapter refuses"
    elif not selects_by_site:
        assert declared.spatial_subset, f"{dataset_id} accepts a bbox it does not declare"


def _expected_failure(fail: bool, error: type[BaseException]) -> AbstractContextManager[object]:
    """Expect ``error`` from the fetch exchange, or nothing at all."""
    return _raises(error) if fail else nullcontext()


def check_fetch_lifecycle(
    adapter_factory: AdapterFactory,
    scenario_query: Query,
    client_factory: ClientFactory,
    *,
    expected_bytes: bytes,
    arm_download: Callable[[str], None] | None = None,
    injected: bool = False,
    fail: bool = False,
    fetch_error: type[BaseException] = httpx.HTTPStatusError,
    work_dir: Path | None = None,
) -> None:
    """Listing, fetching, and client ownership for one scenario query.

    Listing is repeatable and writes nothing, assets identify themselves and
    their dataset, a fetch writes the exact bytes to the exact path it was given
    and nothing beside it, and one client serves the whole exchange. With
    ``injected`` the caller supplies that client and still owns it afterwards;
    with ``fail`` the transport refuses the download, which must propagate and
    leave no partial file behind.

    ``arm_download`` receives the HTTPS URL the chosen asset will be fetched
    from, which the caller's mock transport needs before ``fetch`` runs.
    """
    data = expected_bytes
    clients: list[httpx.Client] = []

    def make_client() -> httpx.Client:
        client = client_factory()
        clients.append(client)
        return client

    with _work_dir(work_dir) as root, _isolated_cache(root), _patched_client(make_client):
        adapter = adapter_factory()
        assert clients == []  # Construction is lazy.
        supplied = make_client() if injected else None
        if supplied is not None:
            adapter = adapter_factory(client=supplied)
        try:
            with _expected_failure(fail, fetch_error), adapter:
                first = adapter.list_assets(scenario_query)
                assert len(first) == 1
                assert first == adapter.list_assets(scenario_query)
                assert {a.dataset_id for a in first} == {adapter.dataset.id}
                assert len({a.id for a in first}) == len(first)
                assert all(a.id and a.href and a.time and a.time.start for a in first)
                assert all(a.size is None or a.size == len(data) for a in first)
                assert list(root.iterdir()) == []  # Listing never writes cache/provenance.
                asset = first[0]
                if arm_download is not None:
                    arm_download(_download_url(asset.href))
                dest = root / "chosen-output"
                assert adapter.fetch(asset, dest) == dest
                assert dest.read_bytes() == data
                assert list(root.iterdir()) == [dest]  # No provider-owned sidecars.
                assert len(clients) == 1
            if fail:
                assert list(root.iterdir()) == []
            assert len(clients) == 1
            assert clients[0].is_closed is not injected
            adapter.close()  # Repeated cleanup remains safe.
            assert clients[0].is_closed is not injected
        finally:
            if supplied is not None:
                supplied.close()


def check_provider_contract(
    dataset: Dataset,
    adapter_factory: AdapterFactory,
    scenario_query: Query,
    *,
    client_factory: ClientFactory,
    expected_bytes: bytes,
    arm_download: Callable[[str], None] | None = None,
    timed_query: Query | None = None,
    failing_client_factory: ClientFactory | None = None,
    fetch_error: type[BaseException] = httpx.HTTPStatusError,
    work_dir: Path | None = None,
) -> None:
    """Run every contract check against one adapter and one scenario query.

    ``scenario_query`` is a query the adapter resolves to exactly one asset;
    ``timed_query`` is the same scenario with a window even where the adapter
    refuses one, and defaults to ``scenario_query``. Supplying
    ``failing_client_factory``, whose transport refuses the download, also runs
    the failure half of the fetch lifecycle. The individual ``check_*``
    functions are public too, for a suite that wants one test per rule.
    """
    check_params_declaration(adapter_factory)
    check_declared_params(adapter_factory, scenario_query)
    check_text_refused(adapter_factory, scenario_query)
    check_invalid_params_refused(adapter_factory, scenario_query)
    if scenario_query.time is not None:
        check_utc_equivalence(adapter_factory, scenario_query, client_factory)
    check_declared_capabilities(
        dataset, adapter_factory, scenario_query, timed_query or scenario_query
    )
    for injected in (False, True):
        check_fetch_lifecycle(
            adapter_factory,
            scenario_query,
            client_factory,
            expected_bytes=expected_bytes,
            arm_download=arm_download,
            injected=injected,
            work_dir=work_dir,
        )
        if failing_client_factory is not None:
            check_fetch_lifecycle(
                adapter_factory,
                scenario_query,
                failing_client_factory,
                expected_bytes=expected_bytes,
                arm_download=arm_download,
                injected=injected,
                fail=True,
                fetch_error=fetch_error,
                work_dir=work_dir,
            )


__all__ = [
    "PARTIAL_PARAM",
    "PROBE_BBOX",
    "REFUSED",
    "SELECTORS",
    "AdapterFactory",
    "ClientFactory",
    "TransportReached",
    "check_declared_capabilities",
    "check_declared_params",
    "check_fetch_lifecycle",
    "check_invalid_params_refused",
    "check_params_declaration",
    "check_provider_contract",
    "check_text_refused",
    "check_utc_equivalence",
]
