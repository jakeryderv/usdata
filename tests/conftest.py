from __future__ import annotations

import socket

import pytest

from usdata.protocols import http


@pytest.fixture(autouse=True)
def offline_unit_tests(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject real connections in unit tests, even when integration tests are enabled."""
    if request.node.get_closest_marker("integration"):
        return

    def blocked(*args, **kwargs):
        raise AssertionError(
            "unit tests must not access the network; mock HTTP or mark integration"
        )

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(http, "sleep", lambda delay: None)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run tests that hit live services",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-integration"):
        return
    skip = pytest.mark.skip(reason="needs --run-integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
