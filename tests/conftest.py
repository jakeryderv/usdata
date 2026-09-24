from __future__ import annotations

import json
import socket
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import httpx
import pytest

from usdata.models import (
    Asset,
    CredentialSpec,
    Dataset,
    Protocol,
    Query,
    Status,
    TimeRange,
    Variable,
)
from usdata.protocols import http
from usdata.providers import HttpProvider
from usdata.registry import Registry


@pytest.fixture(autouse=True)
def offline_tests(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject real connections outside explicitly opted-in live tests."""
    if request.node.get_closest_marker("live"):
        return

    def blocked(*args, **kwargs):
        raise AssertionError("offline tests must not access the network; mock HTTP or mark live")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(http, "sleep", lambda delay: None)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-live",
        "--run-integration",
        dest="run_live",
        action="store_true",
        default=False,
        help="run tests that hit live services (--run-integration is a compatibility alias)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    defaults = {"unit": "l0", "adapters": "l1", "protocols": "l1", "component": "l2", "live": "l4"}
    root = Path(__file__).parent
    for item in items:
        # Keep the old marker usable while callers migrate to `live`.
        live = item.get_closest_marker("live") or item.get_closest_marker("integration")
        if live:
            item.add_marker(pytest.mark.live)
            item.add_marker(pytest.mark.integration)
        levels = {name for name in set(defaults.values()) | {"l3"} if item.get_closest_marker(name)}
        if not levels:
            level = "l4" if live else defaults[Path(item.path).relative_to(root).parts[0]]
            item.add_marker(getattr(pytest.mark, level))
            levels = {level}
        if len(levels) != 1 or (live and levels != {"l4"}) or (not live and levels == {"l4"}):
            raise pytest.UsageError(f"{item.nodeid}: declare exactly one consistent test level")
        if live and not config.getoption("run_live"):
            item.add_marker(pytest.mark.skip(reason="needs --run-live"))


KEYED_EMAIL = "USDATA_TEST_EMAIL"
KEYED_KEY = "USDATA_TEST_KEY"
KEYED_URL = "https://keyed.example.test/data?station=A1"
KEYED_MODULE = "usdata_test_keyed"


def _canonical(body: dict[str, object]) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


class KeyedSource(HttpProvider):
    """A source like AQS: keys ride in the query string, and the response echoes the request.

    It adds the keys only as it sends the request, drops the echoed URL before
    writing, and redacts errors, so it meets ADR 0039. Tests subclass it to
    break one rule at a time.
    """

    transformations = ("json: dropped the echoed request url; keys sorted",)
    url = KEYED_URL

    def list_assets(self, query: Query) -> list[Asset]:
        self.check_params(query)
        self.reject(query, "text", "bbox", "variables", "time", hint="the station is fixed")
        return [self.asset(self.url)]

    def asset(self, href: str) -> Asset:
        start = datetime(2024, 1, 1, tzinfo=UTC)
        return Asset(
            id="keyed.json",
            dataset_id=self.dataset.id,
            href=href,
            protocol=Protocol.HTTP,
            media_type="application/json",
            time=TimeRange(start=start, end=start),
        )

    def keys(self) -> dict[str, str]:
        return {"email": self.credentials[KEYED_EMAIL], "key": self.credentials[KEYED_KEY]}

    def fetch(self, asset: Asset, dest: Path) -> Path:
        with self.redacted_errors():
            response = http.get(keyed_url(asset.href, self.keys()), self._http())
        body = response.json()
        body.pop("url", None)
        dest.write_bytes(_canonical(body))
        return dest


def keyed_url(href: str, keys: dict[str, str]) -> httpx.URL:
    """``href`` with the keys added; httpx's ``params=`` would replace its query instead."""
    return httpx.URL(href).copy_merge_params(keys)


def keyed_response(request: httpx.Request, *, fail: bool = False) -> httpx.Response:
    """What the keyed service answers: data with the request echoed, or a 403 that echoes it too.

    A request that lost the selection in its href is refused, as a real service would.
    """
    if "station" not in request.url.params:
        return httpx.Response(400, json={"url": str(request.url), "error": "station missing"})
    if fail or "key" not in request.url.params:
        return httpx.Response(403, json={"url": str(request.url), "error": "invalid key"})
    return httpx.Response(200, json={"url": str(request.url), "data": [1, 2]})


@dataclass(frozen=True)
class Keyed:
    """The fake keyed source: its registry entry, adapter class, and what a fetch writes."""

    dataset: Dataset
    adapter: type[KeyedSource]
    data: bytes
    variables: tuple[str, str] = (KEYED_EMAIL, KEYED_KEY)
    url: str = KEYED_URL
    respond: Callable[..., httpx.Response] = keyed_response

    @property
    def registry(self) -> Registry:
        return Registry([self.dataset])


@pytest.fixture
def keyed(monkeypatch: pytest.MonkeyPatch) -> Keyed:
    """A credentialed dataset whose adapter ``load_adapter`` can import, and no keys set."""
    module = ModuleType(KEYED_MODULE)
    module.KeyedSource = KeyedSource  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, KEYED_MODULE, module)
    for name in (KEYED_EMAIL, KEYED_KEY):
        monkeypatch.delenv(name, raising=False)
    dataset = Dataset(
        id="test:keyed",
        provider="test",
        title="Keyed test source",
        summary="Keyed test source",
        formats=["JSON"],
        protocol=Protocol.HTTP,
        domain="test",
        status=Status.AVAILABLE,
        since="0.1",
        adapter=f"{KEYED_MODULE}:KeyedSource",
        variables=[Variable(name="data")],
        credentials=CredentialSpec(
            variables=[KEYED_EMAIL, KEYED_KEY], signup="https://keyed.example.test/signup"
        ),
    )
    return Keyed(dataset=dataset, adapter=KeyedSource, data=_canonical({"data": [1, 2]}))
