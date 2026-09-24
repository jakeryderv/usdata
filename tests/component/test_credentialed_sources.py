"""Sources that need credentials, through the core: loading, pulling, restoring (ADR 0039)."""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata import doctor, fetch
from usdata.cli import app
from usdata.manifest import Lockfile, lockfile_path
from usdata.mirror import ENV_VAR as MIRROR_ENV_VAR
from usdata.mirror import object_url
from usdata.models import Query, Status
from usdata.providers import MissingCredentials, load_adapter
from usdata.providers.http import HTTPX_LOGGER
from usdata.pull import plan, pull
from usdata.registry import Registry

cli_module = importlib.import_module("usdata.cli.app")
pull_module = importlib.import_module("usdata.pull")
EMAIL, KEY = "someone+aqs@example.org", "k3y-VALUE-9"
MIRROR = "https://data.example.test"
KEYED_ONLY = """
name: keyed
sources:
  - dataset: test:keyed
"""
OPEN_THEN_KEYED = """
name: mixed
sources:
  - dataset: test:open
  - dataset: test:keyed
"""


@pytest.fixture
def mixed(keyed, monkeypatch: pytest.MonkeyPatch) -> Registry:
    """The keyed source beside an anonymous one served by the same host."""

    class OpenSource(keyed.adapter):
        url = keyed.url.replace("A1", "B2")

        def keys(self) -> dict[str, str]:
            return {"key": "public"}

    module = sys.modules[keyed.dataset.adapter.partition(":")[0]]
    monkeypatch.setattr(module, "OpenSource", OpenSource, raising=False)
    anonymous = keyed.dataset.model_copy(
        update={
            "id": "test:open",
            "credentials": None,
            "adapter": keyed.dataset.adapter.replace("KeyedSource", "OpenSource"),
        }
    )
    return Registry([anonymous, keyed.dataset])


@pytest.fixture
def with_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USDATA_TEST_EMAIL", EMAIL)
    monkeypatch.setenv("USDATA_TEST_KEY", KEY)


@pytest.fixture
def no_mirror(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(MIRROR_ENV_VAR, raising=False)


def serve(mock: respx.MockRouter, keyed, *, fail: bool = False) -> respx.Route:
    """Answer the keyed host as the service would: 200 with a key, 403 without or on ``fail``."""
    return mock.get(url__startswith=keyed.url.partition("?")[0]).mock(
        side_effect=lambda request: keyed.respond(request, fail=fail)
    )


def leaked(text: str) -> bool:
    return any(form in text for form in (EMAIL, KEY, "someone%2Baqs%40example.org"))


def write(tmp_path: Path, text: str) -> Path:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(text)
    return manifest


def pinned(keyed, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str = KEYED_ONLY):
    """Pull ``text`` with keys set, then unset them; return the manifest, cache, and registry."""
    manifest, root = write(tmp_path, text), tmp_path / "cache"
    registry = Registry([keyed.dataset])
    monkeypatch.setenv("USDATA_TEST_EMAIL", EMAIL)
    monkeypatch.setenv("USDATA_TEST_KEY", KEY)
    with respx.mock() as mock:
        serve(mock, keyed)
        pull(manifest, root=root, registry=registry)
    monkeypatch.delenv("USDATA_TEST_EMAIL")
    monkeypatch.delenv("USDATA_TEST_KEY")
    return manifest, root, registry


def test_load_adapter_reads_the_declared_variables_from_the_environment(keyed, with_keys) -> None:
    with load_adapter(keyed.dataset) as adapter:
        assert dict(adapter.credentials) == {"USDATA_TEST_EMAIL": EMAIL, "USDATA_TEST_KEY": KEY}
        assert not leaked(repr(adapter.credentials))


def test_load_adapter_refuses_an_unset_or_blank_variable(keyed, monkeypatch) -> None:
    monkeypatch.setenv("USDATA_TEST_EMAIL", EMAIL)
    monkeypatch.setenv("USDATA_TEST_KEY", "  ")
    with pytest.raises(MissingCredentials, match=r"needs USDATA_TEST_KEY set.*keyed.example.test"):
        load_adapter(keyed.dataset)


def test_a_fetch_records_the_variable_names_and_the_transformation(
    keyed, with_keys, tmp_path
) -> None:
    with respx.mock() as mock:
        route = serve(mock, keyed)
        (item,) = fetch(keyed.dataset, Query(), root=tmp_path)
    assert route.call_count == 1 and route.calls[0].request.url.params["key"] == KEY
    assert item.path.read_bytes() == keyed.data
    assert item.provenance.credentials == ["USDATA_TEST_EMAIL", "USDATA_TEST_KEY"]
    assert item.provenance.transformations == list(keyed.adapter.transformations)
    assert item.provenance.source_url == keyed.url
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert not leaked(path.read_text()), path


def test_a_failed_request_raises_without_the_key(keyed, with_keys, tmp_path) -> None:
    with respx.mock() as mock, pytest.raises(httpx.HTTPStatusError) as caught:
        serve(mock, keyed, fail=True)
        fetch(keyed.dataset, Query(), root=tmp_path)
    error = caught.value
    assert error.response.status_code == 403 and "email=***&key=***" in str(error)
    assert not leaked(f"{error} {error.request.url} {error.response.text}")
    assert not list(tmp_path.rglob("*.json"))


def test_the_httpx_request_log_is_redacted_while_an_adapter_is_open(
    keyed, with_keys, tmp_path, caplog
) -> None:
    logger = logging.getLogger(HTTPX_LOGGER)
    before = list(logger.filters)
    with caplog.at_level(logging.INFO, logger=HTTPX_LOGGER), respx.mock() as mock:
        serve(mock, keyed)
        fetch(keyed.dataset, Query(), root=tmp_path)
    lines = [record.getMessage() for record in caplog.records if record.name == HTTPX_LOGGER]
    assert lines and all("key=***" in line and not leaked(line) for line in lines)
    assert logger.filters == before  # Closing the adapter removed its filter.


def test_pull_refuses_a_missing_key_before_fetching_any_source(mixed, tmp_path) -> None:
    manifest = write(tmp_path, OPEN_THEN_KEYED)
    with respx.mock() as mock, pytest.raises(MissingCredentials, match="test:keyed"):
        pull(manifest, root=tmp_path / "cache", registry=mixed)
    assert not mock.calls and not lockfile_path(manifest).exists()
    with respx.mock() as mock, pytest.raises(MissingCredentials):
        plan(manifest, registry=mixed)
    assert not mock.calls


def test_a_pulled_lockfile_sidecar_and_plan_hold_no_key(keyed, mixed, with_keys, tmp_path) -> None:
    manifest = write(tmp_path, OPEN_THEN_KEYED)
    with respx.mock() as mock:
        serve(mock, keyed)
        result = pull(manifest, root=tmp_path / "cache", registry=mixed)
        planned = plan(manifest, registry=mixed)
    assert not leaked(lockfile_path(manifest).read_text())
    assert not leaked(planned.model_dump_json())
    open_entry, keyed_entry = Lockfile.load(lockfile_path(manifest)).assets
    assert keyed_entry.provenance.credentials == ["USDATA_TEST_EMAIL", "USDATA_TEST_KEY"]
    assert open_entry.provenance.credentials == []
    assert [item.asset.dataset_id for item in result.fetched] == ["test:open", "test:keyed"]
    for path in (tmp_path / "cache").rglob("*"):
        if path.is_file():
            assert not leaked(path.read_text()), path


def test_a_cached_restore_needs_no_key(keyed, tmp_path, monkeypatch) -> None:
    manifest, root, registry = pinned(keyed, tmp_path, monkeypatch)
    with respx.mock() as mock:
        result = pull(manifest, root=root, registry=registry)
    assert not mock.calls and result.from_lockfile and result.fetched[0].from_cache
    assert result.unchecked == []


def test_without_a_key_or_a_mirror_an_uncached_restore_is_refused(
    keyed, tmp_path, monkeypatch, no_mirror
) -> None:
    manifest, root, registry = pinned(keyed, tmp_path, monkeypatch)
    (path,) = [p for p in root.rglob("keyed.json")]
    path.unlink()
    with respx.mock() as mock, pytest.raises(MissingCredentials, match="USDATA_TEST_EMAIL"):
        pull(manifest, root=root, registry=registry)
    assert not mock.calls


def test_without_a_key_the_mirror_restores_a_pinned_entry_unchecked(
    keyed, tmp_path, monkeypatch
) -> None:
    manifest, root, registry = pinned(keyed, tmp_path, monkeypatch)
    (path,) = [p for p in root.rglob("keyed.json")]
    entry = Lockfile.load(lockfile_path(manifest)).assets[0]
    path.unlink()
    monkeypatch.setenv(MIRROR_ENV_VAR, MIRROR)
    mirrored = object_url(MIRROR, entry.provenance.checksum)
    with respx.mock(assert_all_called=False) as mock:
        source = serve(mock, keyed)
        mock.get(mirrored).respond(200, content=keyed.data)
        result = pull(manifest, root=root, registry=registry)
    assert not source.called
    assert result.mirrored == ["keyed.json"] and result.unchecked == ["keyed.json"]
    (item,) = result.fetched
    assert item.path.read_bytes() == keyed.data and item.provenance.mirror == mirrored
    assert item.provenance.credentials == ["USDATA_TEST_EMAIL", "USDATA_TEST_KEY"]
    assert Lockfile.load(lockfile_path(manifest)).assets[0] == entry  # The pin is unchanged.


def test_without_a_key_a_mirror_miss_is_refused_and_says_so(keyed, tmp_path, monkeypatch) -> None:
    manifest, root, registry = pinned(keyed, tmp_path, monkeypatch)
    (path,) = [p for p in root.rglob("keyed.json")]
    entry = Lockfile.load(lockfile_path(manifest)).assets[0]
    path.unlink()
    monkeypatch.setenv(MIRROR_ENV_VAR, MIRROR)
    with respx.mock() as mock, pytest.raises(MissingCredentials) as caught:
        mock.get(object_url(MIRROR, entry.provenance.checksum)).respond(404)
        pull(manifest, root=root, registry=registry)
    assert str(caught.value).endswith(
        "the mirror could not restore keyed.json either (not mirrored (404))"
    )
    assert not path.exists()


def test_an_update_without_a_key_is_refused_before_any_fetch(
    keyed, mixed, tmp_path, monkeypatch
) -> None:
    manifest, root = write(tmp_path, OPEN_THEN_KEYED), tmp_path / "cache"
    monkeypatch.setenv("USDATA_TEST_EMAIL", EMAIL)
    monkeypatch.setenv("USDATA_TEST_KEY", KEY)
    with respx.mock() as mock:
        serve(mock, keyed)
        pull(manifest, root=root, registry=mixed)
    monkeypatch.delenv("USDATA_TEST_KEY")
    for path in root.rglob("*.json"):
        if not path.name.endswith(".provenance.json"):
            path.unlink()
    with respx.mock() as mock, pytest.raises(MissingCredentials):
        pull(manifest, root=root, registry=mixed, update=["test:keyed"])
    assert not mock.calls  # The anonymous entry was not restored first.


def test_cli_info_names_the_variables_and_where_to_get_a_key(keyed, monkeypatch) -> None:
    monkeypatch.setattr(cli_module, "default_registry", lambda: Registry([keyed.dataset]))
    result = CliRunner().invoke(app, ["info", "test:keyed"])
    assert result.exit_code == 0, result.output
    assert "credentials: USDATA_TEST_EMAIL, USDATA_TEST_KEY (environment)" in result.stdout
    assert "key:       https://keyed.example.test/signup" in result.stdout


def test_cli_pull_without_a_key_exits_2_naming_it(keyed, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(pull_module, "default_registry", lambda: Registry([keyed.dataset]))
    manifest = write(tmp_path, KEYED_ONLY)
    with respx.mock() as mock:
        result = CliRunner().invoke(app, ["pull", str(manifest), "--no-progress"])
    assert result.exit_code == 2 and not mock.calls
    assert "test:keyed needs USDATA_TEST_EMAIL, USDATA_TEST_KEY set" in result.output


def test_cli_pull_reports_entries_restored_unchecked(keyed, tmp_path, monkeypatch) -> None:
    manifest, root, registry = pinned(keyed, tmp_path, monkeypatch)
    monkeypatch.setattr(pull_module, "default_registry", lambda: registry)
    entry = Lockfile.load(lockfile_path(manifest)).assets[0]
    for path in root.rglob("keyed.json"):
        path.unlink()
    monkeypatch.setenv(MIRROR_ENV_VAR, MIRROR)
    with respx.mock() as mock:
        mock.get(object_url(MIRROR, entry.provenance.checksum)).respond(200, content=keyed.data)
        result = CliRunner().invoke(
            app, ["pull", str(manifest), "--cache-dir", str(root), "--no-progress"]
        )
    assert result.exit_code == 0, result.output
    assert "\tmirrored\t" in result.stdout
    assert "1 asset(s) were restored from the mirror without asking their source" in result.output
    assert "changed upstream" not in result.output


def test_doctor_reports_whether_keys_are_set_and_never_their_values(keyed, monkeypatch) -> None:
    planned = keyed.dataset.model_copy(
        update={"id": "test:later", "status": Status.PLANNED, "since": None, "target": "later"}
    )
    registry = Registry([keyed.dataset, planned.model_copy(update={"adapter": None})])
    monkeypatch.setenv("USDATA_TEST_EMAIL", EMAIL)
    (check,) = doctor._credential_checks(registry)
    assert (check.name, check.status) == ("credentials:test:keyed", doctor.CheckStatus.WARN)
    assert (
        check.detail == "USDATA_TEST_KEY unset; request a key at https://keyed.example.test/signup"
    )
    monkeypatch.setenv("USDATA_TEST_KEY", KEY)
    (check,) = doctor._credential_checks(registry)
    assert check.status is doctor.CheckStatus.OK
    assert check.detail == "USDATA_TEST_EMAIL, USDATA_TEST_KEY set" and not leaked(check.detail)
