import importlib
import os
import shutil
from pathlib import Path

import pytest

from usdata import build_query, provenance
from usdata.cache import sha256_file
from usdata.fetch import ChecksumMismatch, fetch, fetch_asset
from usdata.models import Asset, Protocol

# ``usdata.fetch`` names the function once the package root exports it; fetch the module itself.
fetch_module = importlib.import_module("usdata.fetch")


def _rewrite_after_sidecar(path: Path, data: bytes) -> None:
    """Replace a cached file's bytes and leave it plainly newer than its sidecar.

    Filesystem timestamp granularity varies, so the mtime is set explicitly:
    the test is about the trust rule, not about clock resolution.
    """
    path.write_bytes(data)
    newer = provenance.sidecar_path(path).stat().st_mtime_ns + 1_000_000
    os.utime(path, ns=(newer, newer))


def _forbid_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(path: Path) -> str:
        raise AssertionError(f"a trusted cache hit must not hash {path}")

    monkeypatch.setattr(fetch_module, "sha256_file", refuse)


def test_cached_asset_honors_new_checksum_and_preserves_old_file(
    tmp_path: Path, fake_source
) -> None:
    ds, state = fake_source
    asset = Asset(
        id="data", dataset_id=ds.id, href="https://example.test/bytes", protocol=Protocol.HTTP
    )
    original = fetch_asset(ds, asset, root=tmp_path)
    pinned = asset.model_copy(update={"checksum": "sha256:" + "0" * 64})
    with pytest.raises(ChecksumMismatch):
        fetch_asset(ds, pinned, root=tmp_path)
    assert state["fetches"] == 2
    assert original.path.read_bytes() == b"original"
    assert provenance.read(original.path) == original.provenance
    assert not list(tmp_path.rglob("*.part"))


def test_core_cache_and_cleanup_use_only_provider_contract(tmp_path: Path, fake_source) -> None:
    ds, state = fake_source
    (first,) = fetch(ds, build_query(), root=tmp_path)
    (second,) = fetch(ds, build_query(), root=tmp_path)
    assert not first.from_cache and second.from_cache
    assert first.provenance == second.provenance
    assert state == {"fetches": 1, "closed": 2}
    _rewrite_after_sidecar(first.path, b"tampered")
    (repaired,) = fetch(ds, build_query(), root=tmp_path)
    assert not repaired.from_cache and repaired.path.read_bytes() == b"original"
    assert state == {"fetches": 2, "closed": 3}


def test_untouched_cache_hit_is_trusted_without_hashing(
    tmp_path: Path, fake_source, monkeypatch: pytest.MonkeyPatch
) -> None:
    ds, state = fake_source
    (first,) = fetch(ds, build_query(), root=tmp_path)
    _forbid_hashing(monkeypatch)
    (second,) = fetch(ds, build_query(), root=tmp_path)
    assert second.from_cache and second.provenance == first.provenance
    assert state["fetches"] == 1


def test_file_touched_after_its_sidecar_is_hashed_and_refetched(
    tmp_path: Path, fake_source, monkeypatch: pytest.MonkeyPatch
) -> None:
    ds, state = fake_source
    (first,) = fetch(ds, build_query(), root=tmp_path)
    # Same size as the original bytes, so only the hash can tell them apart.
    _rewrite_after_sidecar(first.path, b"TAMPERED")
    assert first.path.stat().st_size == first.provenance.size
    hashed: list[Path] = []

    def counting(path: Path) -> str:
        hashed.append(path)
        return sha256_file(path)

    monkeypatch.setattr(fetch_module, "sha256_file", counting)
    (repaired,) = fetch(ds, build_query(), root=tmp_path)
    assert hashed == [first.path]
    assert not repaired.from_cache and repaired.path.read_bytes() == b"original"
    assert state["fetches"] == 2


def test_copied_cache_with_identical_mtimes_is_trusted(
    tmp_path: Path, fake_source, monkeypatch: pytest.MonkeyPatch
) -> None:
    ds, state = fake_source
    source_root = (tmp_path / "source").resolve()
    (first,) = fetch(ds, build_query(), root=source_root)
    copied_root = (tmp_path / "copied").resolve()
    shutil.copytree(source_root, copied_root)
    copied = copied_root / first.path.relative_to(source_root)
    # A copy that lands both files in the same instant must still be a cache hit.
    for target in (copied, provenance.sidecar_path(copied)):
        os.utime(target, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
    _forbid_hashing(monkeypatch)
    (restored,) = fetch(ds, build_query(), root=copied_root)
    assert restored.from_cache and restored.path == copied
    assert state["fetches"] == 1
