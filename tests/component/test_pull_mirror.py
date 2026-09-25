"""A configured mirror restores pinned bytes the source no longer serves (ADR 0030)."""

from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata import provenance
from usdata.cli import app
from usdata.manifest import Lockfile, lockfile_path
from usdata.mirror import ENV_VAR, MirrorMismatch, download, mirror_url, object_key, object_url
from usdata.providers.noaa.ghcnd import DATA_URL
from usdata.pull import UpstreamChanged, pull, verify

MANIFEST = """
name: mirrored
sources:
  - dataset: noaa:ghcn-daily
    start: 2024-05-06
    end: 2024-05-07
    params: { stations: USW00013967 }
"""
MIRROR = "https://data.example.test"
V1, V2 = b"a1", b"a2"


@pytest.fixture
def locked(tmp_path: Path) -> tuple[Path, Path, str]:
    """A manifest pulled once against version 1, its cache emptied, and its pin's mirror URL."""
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    root = tmp_path / "cache"
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(200, content=V1)
        (item,) = pull(manifest, root=root).fetched
    item.path.unlink()
    return manifest, root, object_url(MIRROR, item.provenance.checksum)


def test_mirror_keys_are_the_checksum_and_nothing_else() -> None:
    digest = "ab" * 32
    assert object_key(f"sha256:{digest}") == f"sha256/{digest}"
    assert object_url(MIRROR + "/", f"sha256:{digest}") == f"{MIRROR}/sha256/{digest}"
    for bad in ("md5:abc", "sha256:short", digest):
        with pytest.raises(ValueError, match="not a sha256 checksum"):
            object_key(bad)


def test_mirror_is_off_unless_the_environment_names_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert mirror_url() is None
    monkeypatch.setenv(ENV_VAR, "  ")
    assert mirror_url() is None
    monkeypatch.setenv(ENV_VAR, f"{MIRROR}/")
    assert mirror_url() == MIRROR


def test_without_a_mirror_a_changed_source_is_drift_as_before(
    locked: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, root, _ = locked
    monkeypatch.delenv(ENV_VAR, raising=False)
    with respx.mock() as mock, pytest.raises(UpstreamChanged) as info:
        mock.get(DATA_URL).respond(200, content=V2)
        pull(manifest, root=root)
    assert [d.problem for d in info.value.drift] == ["upstream changed"]


def test_mirror_restores_the_pinned_bytes_and_the_sidecar_says_so(
    locked: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, root, mirror_object = locked
    monkeypatch.setenv(ENV_VAR, MIRROR)
    before = lockfile_path(manifest).read_bytes()
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(200, content=V2)
        served = mock.get(mirror_object).respond(200, content=V1)
        result = pull(manifest, root=root)
    (item,) = result.fetched
    assert served.call_count == 1
    assert result.mirrored == [item.asset.id] and result.from_lockfile
    assert item.path.read_bytes() == V1 and not item.from_cache
    assert item.provenance.mirror == mirror_object
    assert item.provenance.source_url == item.asset.href
    assert provenance.read(item.path).mirror == mirror_object
    assert lockfile_path(manifest).read_bytes() == before
    assert verify(manifest, root=root) == []
    # The lockfile itself never records the mirror: the pin still describes the source.
    (entry,) = Lockfile.load(lockfile_path(manifest)).assets
    assert entry.provenance.mirror is None


@pytest.mark.parametrize(
    ("status", "content", "problem"),
    [
        (404, b"", "upstream changed; not mirrored (404)"),
        (200, b"zz", "upstream changed; mirror mismatch"),
    ],
)
def test_a_mirror_that_cannot_help_leaves_the_entry_as_drift(
    locked: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    content: bytes,
    problem: str,
) -> None:
    manifest, root, mirror_object = locked
    monkeypatch.setenv(ENV_VAR, MIRROR)
    with respx.mock() as mock, pytest.raises(UpstreamChanged) as info:
        mock.get(DATA_URL).respond(200, content=V2)
        mock.get(mirror_object).respond(status, content=content)
        pull(manifest, root=root)
    (drift,) = info.value.drift
    assert drift.problem == problem
    assert not drift.path.exists(), "a mismatching mirror object is never written as the asset"


@pytest.mark.parametrize("status", [404, 410])
def test_mirror_restores_an_object_the_source_no_longer_serves(
    locked: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    manifest, root, mirror_object = locked
    monkeypatch.setenv(ENV_VAR, MIRROR)
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(status)
        mock.get(mirror_object).respond(200, content=V1)
        result = pull(manifest, root=root)
    (item,) = result.fetched
    assert result.mirrored == [item.asset.id]
    assert item.path.read_bytes() == V1
    assert verify(manifest, root=root) == []


@pytest.mark.parametrize("status", [404, 410])
def test_without_a_mirror_a_gone_object_is_drift(
    locked: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    manifest, root, _ = locked
    monkeypatch.delenv(ENV_VAR, raising=False)
    with respx.mock() as mock, pytest.raises(UpstreamChanged) as info:
        mock.get(DATA_URL).respond(status)
        pull(manifest, root=root)
    assert [d.problem for d in info.value.drift] == [f"gone upstream ({status})"]


def test_a_server_error_is_not_drift(
    locked: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, root, mirror_object = locked
    monkeypatch.setenv(ENV_VAR, MIRROR)
    with respx.mock(assert_all_called=False) as mock:
        mock.get(DATA_URL).respond(503)
        mirrored = mock.get(mirror_object).respond(200, content=V1)
        with pytest.raises(httpx.HTTPStatusError):
            pull(manifest, root=root)
    assert not mirrored.called, "a failed request says nothing about the pin"


def test_an_unreachable_mirror_is_reported_with_the_drift(
    locked: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, root, mirror_object = locked
    monkeypatch.setenv(ENV_VAR, MIRROR)
    with respx.mock() as mock, pytest.raises(UpstreamChanged) as info:
        mock.get(DATA_URL).respond(200, content=V2)
        mock.get(mirror_object).mock(side_effect=httpx.ConnectError("down"))
        pull(manifest, root=root)
    (drift,) = info.value.drift
    assert drift.problem == "upstream changed; mirror unreachable (ConnectError)"


def test_mirror_download_verifies_what_it_is_named_for(tmp_path: Path) -> None:
    checksum = "sha256:" + "ab" * 32
    with respx.mock() as mock, httpx.Client() as client:
        mock.get(object_url(MIRROR, checksum)).respond(200, content=b"not those bytes")
        with pytest.raises(MirrorMismatch, match="not the sha256:abab"):
            download(MIRROR, checksum, tmp_path / "object", client)


def test_cli_reports_mirrored_assets_and_exits_zero(
    locked: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, root, mirror_object = locked
    monkeypatch.setenv(ENV_VAR, MIRROR)
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(200, content=V2)
        mock.get(mirror_object).respond(200, content=V1)
        result = CliRunner().invoke(app, ["pull", str(manifest), "--cache-dir", str(root)])
    assert result.exit_code == 0, result.output
    assert "\tmirrored\t" in result.stdout
    assert "restored from the mirror" in result.output and "--update" in result.output
