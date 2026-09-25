import importlib
from pathlib import Path

import pytest
import respx

from usdata import ChecksumMismatch, provenance
from usdata.cache import sha256_file
from usdata.manifest import Lockfile, lockfile_path
from usdata.models import Asset, ByteRange, PartialFetch, Protocol, Provenance, Query
from usdata.protocols.http import ObjectChanged, RangeNotHonored
from usdata.providers.base import Provider
from usdata.providers.noaa.ghcnd import DATA_URL
from usdata.pull import STAGING_DIR, UpstreamChanged, pull, verify
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
        FETCHED.append(asset.id)
        dest.write_bytes(UPSTREAM[asset.id])
        if asset.id in REPUBLISH:
            # The next fetch sees the next version, as if upstream republished in between.
            UPSTREAM[asset.id] = REPUBLISH[asset.id].pop(0)
        return dest


UPSTREAM: dict[str, bytes] = {}
DOWN: set[str] = set()
FETCHED: list[str] = []
REPUBLISH: dict[str, list[bytes]] = {}


class Ranged(Sized):
    """``Sized``, but every asset is read as byte ranges, and a range request can be refused."""

    def prepare_fetch(self, asset: Asset, pinned: Provenance | None = None) -> PartialFetch:
        return PartialFetch(
            object_url=asset.href,
            object_size=100,
            object_etag="etag-v1",
            index_url=asset.href + ".idx",
            index_checksum="sha256:" + "1" * 64,
            messages=[1],
            ranges=[ByteRange(start=0, end=3)],
        )

    def fetch_partial(self, asset: Asset, dest: Path, partial: PartialFetch) -> Path:
        if REFUSE:
            raise REFUSE[0]
        return self.fetch(asset, dest)


REFUSE: list[Exception] = []


@pytest.fixture
def sized() -> Registry:
    """The default registry with ghcn-daily served by ``Sized``, upstream at version 1."""
    return _served_by("Sized")


@pytest.fixture
def ranged() -> Registry:
    """The default registry with ghcn-daily served by ``Ranged``, upstream at version 1."""
    return _served_by("Ranged")


def _served_by(adapter: str) -> Registry:
    UPSTREAM.clear()
    UPSTREAM.update(a=b"a-v1", b=b"b-v1")
    DOWN.clear()
    FETCHED.clear()
    REPUBLISH.clear()
    REFUSE.clear()
    reg = default_registry()
    dataset = reg.get("noaa:ghcn-daily").model_copy(update={"adapter": f"{__name__}:{adapter}"})
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


@pytest.mark.parametrize("how", ["force", "update"])
def test_a_staged_run_fetches_an_asset_two_sources_share_once(
    tmp_path: Path, sized: Registry, how: str
) -> None:
    """Upstream republishing mid-run cannot leave the two entries pinning different bytes."""
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("name: shared\nsources:\n" + day("2024-05-06") + day("2024-05-06"))
    root = tmp_path / "cache"
    pull(manifest, root=root, registry=sized)
    FETCHED.clear()
    # A new size, so the forced re-resolve cannot trust the cached copy.
    UPSTREAM["a"] = b"a-version-2"
    REPUBLISH["a"] = [b"a-version-3"]
    if how == "force":
        result = pull(manifest, root=root, registry=sized, force=True)
    else:
        result = pull(manifest, root=root, registry=sized, update=["a"])
        assert result.updated == ["a", "a"]
    assert FETCHED == ["a"]
    assert [item.path.read_bytes() for item in result.fetched] == [b"a-version-2"] * 2
    pins = {entry.provenance.checksum for entry in Lockfile.load(lockfile_path(manifest)).assets}
    assert len(pins) == 1
    assert [entry.source for entry in result.lockfile.assets] == ["1", "2"]
    assert verify(manifest, root=root) == []


def test_a_refused_range_is_drift(tmp_path: Path, ranged: Registry) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("name: ranged\nsources:\n" + day("2024-05-06"))
    root = tmp_path / "cache"
    (item,) = pull(manifest, root=root, registry=ranged).fetched
    item.path.unlink()
    REFUSE.append(RangeNotHonored("https://example.test/a ignored the range"))
    with pytest.raises(UpstreamChanged) as info:
        pull(manifest, root=root, registry=ranged)
    assert [d.problem for d in info.value.drift] == ["range refused"]


def test_updating_a_republished_partial_asset_says_to_force(
    tmp_path: Path, ranged: Registry
) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("name: ranged\nsources:\n" + day("2024-05-06"))
    root = tmp_path / "cache"
    pull(manifest, root=root, registry=ranged)
    before = lockfile_path(manifest).read_bytes()
    REFUSE.append(ObjectChanged("https://example.test/a was republished"))
    with pytest.raises(ObjectChanged, match="pull with force"):
        pull(manifest, root=root, registry=ranged, update=["a"])
    assert lockfile_path(manifest).read_bytes() == before


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
