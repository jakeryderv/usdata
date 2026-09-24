from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx
import pytest

from usdata.models import Asset, Query, TimeRange
from usdata.protocols import http
from usdata.providers import Credentials, MissingCredentials
from usdata.testing import (
    check_credentials_contained,
    check_credentials_required,
    check_provider_contract,
    sentinel_credentials,
)


def transports(keyed):
    def build(*, fail: bool = False) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(lambda r: keyed.respond(r, fail=fail)))

    return build


def factory_for(keyed, cls: type | None = None):
    sentinels = sentinel_credentials(keyed.dataset)
    adapter = cls or keyed.adapter

    def build(client: httpx.Client | None = None, credentials: Credentials = sentinels):
        return adapter(keyed.dataset, client, credentials=credentials)

    return build


def variant(keyed, **methods: Any) -> type:
    """The well-behaved keyed source with the given methods replaced, to break one rule."""
    return type("Variant", (keyed.adapter,), methods)


def contained(keyed, cls: type, tmp_path: Path) -> None:
    transport = transports(keyed)
    check_credentials_contained(
        keyed.dataset,
        factory_for(keyed, cls),
        Query(),
        transport,
        failing_client_factory=lambda: transport(fail=True),
        work_dir=tmp_path,
    )


def test_a_source_that_keeps_its_keys_in_passes_the_whole_contract(keyed, tmp_path) -> None:
    check_provider_contract(
        keyed.dataset,
        factory_for(keyed),
        Query(),
        client_factory=transports(keyed),
        expected_bytes=keyed.data,
        timed_query=Query(time=TimeRange.model_validate({"start": "2024-01-01T00:00:00Z"})),
        failing_client_factory=lambda: transports(keyed)(fail=True),
        work_dir=tmp_path,
    )


def test_sentinels_cover_every_declared_variable_in_encodable_forms(keyed) -> None:
    sentinels = sentinel_credentials(keyed.dataset)
    assert set(sentinels) == set(keyed.variables)
    assert all("@" in value and "+" in value for value in sentinels.values())


def _ignoring_missing_keys(self: Any, dataset, client=None, *, credentials=None) -> None:
    """Build without the base check, as an adapter overriding __init__ carelessly might."""
    self.dataset = dataset
    self.credentials = credentials or Credentials()
    self._client, self._owns_client, self._log_filter = client, client is None, None


def test_an_adapter_that_can_be_built_without_its_keys_is_caught(keyed) -> None:
    check_credentials_required(keyed.dataset, factory_for(keyed))
    with pytest.raises(pytest.fail.Exception, match="DID NOT RAISE"):
        careless = variant(keyed, __init__=_ignoring_missing_keys)
        check_credentials_required(keyed.dataset, factory_for(keyed, careless))


def test_a_missing_key_is_refused_before_a_client_exists(keyed, monkeypatch) -> None:
    def unexpected() -> httpx.Client:
        raise AssertionError("no client before the credential check")

    monkeypatch.setattr(http, "client", unexpected)
    with pytest.raises(MissingCredentials):
        keyed.adapter(keyed.dataset, credentials=Credentials({"USDATA_TEST_EMAIL": "a@b"}))


def _key_in_href(self: Any, query: Query) -> list[Asset]:
    return [self.asset(str(httpx.URL(self.url, params=self.keys())))]


def _writes_the_echo(self: Any, asset: Asset, dest: Path) -> Path:
    with self.redacted_errors():
        dest.write_bytes(http.get(asset.href, self._http(), params=self.keys()).content)
    return dest


def _unredacted_errors(self: Any, asset: Asset, dest: Path) -> Path:
    body = http.get(asset.href, self._http(), params=self.keys()).json()
    body.pop("url")
    dest.write_text(json.dumps(body, sort_keys=True, separators=(",", ":")))
    return dest


def _never_sends_keys(self: Any) -> dict[str, str]:
    return {"key": "not-the-credential"}


def _unfiltered_log(self: Any) -> httpx.Client:
    if self._client is None:
        self._client = http.client()
    return self._client


@pytest.mark.parametrize(
    ("methods", "message"),
    [
        ({"list_assets": _key_in_href}, "leaked a credential into"),
        ({"fetch": _writes_the_echo}, "wrote a credential into the fetched bytes"),
        ({"fetch": _unredacted_errors}, "leaked a credential through a failed request"),
        ({"keys": _never_sends_keys}, "never sent its credentials"),
        ({"_http": _unfiltered_log}, "leaked a credential into: HTTP Request"),
    ],
)
def test_each_way_a_key_escapes_is_caught(keyed, tmp_path, methods, message) -> None:
    with pytest.raises(AssertionError, match=message):
        contained(keyed, variant(keyed, **methods), tmp_path)


def test_the_check_restores_httpx_logging_as_it_found_it(keyed, tmp_path) -> None:
    logger = logging.getLogger("httpx")
    level, handlers, filters = logger.level, list(logger.handlers), list(logger.filters)
    contained(keyed, keyed.adapter, tmp_path)
    assert (logger.level, logger.handlers, logger.filters) == (level, handlers, filters)
