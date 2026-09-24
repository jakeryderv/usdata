import importlib
from pathlib import Path

import pytest
import respx

from usdata import ChecksumMismatch, provenance
from usdata.cache import sha256_file
from usdata.manifest import Lockfile, lockfile_path
from usdata.models import Asset, Protocol, Query
from usdata.providers.base import Provider
from usdata.providers.noaa.ghcnd import DATA_URL
from usdata.pull import STAGING_DIR, pull, verify
from usdata.registry import Registry, default_registry

MANIFEST = """name: test
sources:
  - dataset: noaa:ghcn-daily
    start: 2024-05-06
    end: 2024-05-07
    params: {stations: USW00013967}
"""


@pytest.mark.parametrize("damage", ["bytes", "missing_sidecar", "invalid_sidecar", "source"])
def test_new_pull_repairs_cache_before_pinning(tmp_path: Path, damage: str) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    with respx.mock() as mock:
        data = mock.get(DATA_URL).respond(200, content=b"original")
        first = pull(manifest, root=tmp_path / "cache")
        path = first.fetched[0].path
        if damage == "bytes":
            path.write_bytes(b"corrupted")
        elif damage == "missing_sidecar":
            provenance.sidecar_path(path).unlink()
        elif damage == "invalid_sidecar":
            provenance.sidecar_path(path).write_text("{")
        else:
            wrong = first.fetched[0].provenance.model_copy(update={"source_url": "https://wrong/"})
            provenance.write(wrong, path)
        lockfile_path(manifest).unlink()
        repaired = pull(manifest, root=tmp_path / "cache")
        assert data.call_count == 2
    assert not repaired.fetched[0].from_cache
    assert verify(manifest, root=tmp_path / "cache") == []
    assert repaired.fetched[0].provenance.checksum == sha256_file(path)


def test_restore_recovers_sidecar_and_legacy_unpinned_asset(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(200, content=b"original")
        first = pull(manifest, root=tmp_path / "cache")
    item = first.fetched[0]
    provenance.sidecar_path(item.path).unlink()
    with respx.mock():
        restored = pull(manifest, root=tmp_path / "cache")
    assert restored.fetched[0].from_cache
    assert provenance.read(item.path) == item.provenance
    lock = Lockfile.load(lockfile_path(manifest))
    lock.assets[0].asset.checksum = None
    lock.save(lockfile_path(manifest))
    item.path.unlink()
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(200, content=b"changed")
        with pytest.raises(ChecksumMismatch):
            pull(manifest, root=tmp_path / "cache")


def test_restore_rehashes_every_cached_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The lockfile is the reproducibility contract: restore never trusts an mtime."""
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(200, content=b"original")
        first = pull(manifest, root=tmp_path / "cache")
    hashed: list[Path] = []

    def counting(path: Path) -> str:
        hashed.append(path)
        return sha256_file(path)

    # usdata.pull names both a module and a re-exported function; import the module.
    monkeypatch.setattr(importlib.import_module("usdata.pull"), "sha256_file", counting)
    with respx.mock():
        restored = pull(manifest, root=tmp_path / "cache")
    assert restored.from_lockfile and restored.fetched[0].from_cache
    assert first.fetched[0].path in hashed


class Sized(Provider):
    """Lists one sized asset per source day and serves UPSTREAM; a DOWN asset fails to list."""

    def list_assets(self, query: Query) -> list[Asset]:
        assert query.time is not None and query.time.start is not None
        asset_id = "a" if query.time.start.day == 6 else "b"
        if asset_id in DOWN:
            raise RuntimeError(f"{asset_id} unavailable")
        return [
            Asset(
                id=asset_id,
                dataset_id="noaa:ghcn-daily",
                href=f"https://example.test/{asset_id}",
                protocol=Protocol.HTTP,
                size=len(UPSTREAM[asset_id]),
            )
        ]

    def fetch(self, asset: Asset, dest: Path) -> Path:
        dest.write_bytes(UPSTREAM[asset.id])
        return dest


UPSTREAM: dict[str, bytes] = {}
DOWN: set[str] = set()


@pytest.fixture
def sized() -> Registry:
    """The default registry with ghcn-daily served by ``Sized``, upstream at version 1."""
    UPSTREAM.clear()
    UPSTREAM.update(a=b"a-v1", b=b"b-v1")
    DOWN.clear()
    reg = default_registry()
    dataset = reg.get("noaa:ghcn-daily").model_copy(update={"adapter": f"{__name__}:Sized"})
    return Registry(
        [dataset if d.id == dataset.id else d for d in reg],
        providers=[reg.provider(provider_id) for provider_id in sorted(reg.providers())],
        domains=reg.domains(),
        systems=reg.systems(),
    )


def day(date: str) -> str:
    return f"  - dataset: noaa:ghcn-daily\n    start: {date}\n    end: {date}\n"


def test_failed_forced_resolve_keeps_every_cached_file_pinned(
    tmp_path: Path, sized: Registry
) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("name: force\nsources:\n" + day("2024-05-06") + day("2024-05-07"))
    root = tmp_path / "cache"
    first = pull(manifest, root=root, registry=sized)
    original_lock = lockfile_path(manifest).read_bytes()

    # Upstream republishes a with a new size, then b fails during a forced re-resolve.
    UPSTREAM["a"] = b"a-version-2"
    DOWN.add("b")
    with pytest.raises(RuntimeError, match="b unavailable"):
        pull(manifest, root=root, registry=sized, force=True)
    assert lockfile_path(manifest).read_bytes() == original_lock
    assert verify(manifest, root=root) == []  # ADR 0031: absent or matching the lockfile
    assert not any((root / STAGING_DIR).iterdir())

    DOWN.clear()
    forced = pull(manifest, root=root, registry=sized, force=True)
    a = forced.fetched[0]
    assert a.path == first.fetched[0].path and a.path.read_bytes() == b"a-version-2"
    assert provenance.read(a.path) == a.provenance
    assert verify(manifest, root=root) == []
    assert not any((root / STAGING_DIR).iterdir())


def test_forced_resolve_commits_an_asset_two_sources_share_once(
    tmp_path: Path, sized: Registry
) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("name: shared\nsources:\n" + day("2024-05-06") + day("2024-05-06"))
    root = tmp_path / "cache"
    pull(manifest, root=root, registry=sized)
    UPSTREAM["a"] = b"a-version-2"
    forced = pull(manifest, root=root, registry=sized, force=True)
    assert [item.path.read_bytes() for item in forced.fetched] == [b"a-version-2"] * 2
    assert verify(manifest, root=root) == []


def test_failed_first_pull_keeps_what_it_fetched(tmp_path: Path, sized: Registry) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("name: first\nsources:\n" + day("2024-05-06") + day("2024-05-07"))
    root = tmp_path / "cache"
    DOWN.add("b")
    with pytest.raises(RuntimeError, match="b unavailable"):
        pull(manifest, root=root, registry=sized)
    assert not lockfile_path(manifest).exists()
    assert (root / "noaa" / "ghcn-daily" / "a").read_bytes() == b"a-v1"
    assert not (root / STAGING_DIR).exists()
