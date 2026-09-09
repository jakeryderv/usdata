from __future__ import annotations

import socket
from pathlib import Path

import pytest

from usdata.protocols import http


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
