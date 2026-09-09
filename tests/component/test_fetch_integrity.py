from pathlib import Path

import pytest

from usdata import build_query, provenance
from usdata.fetch import ChecksumMismatch, fetch, fetch_asset
from usdata.models import Asset, Protocol


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
    first.path.write_bytes(b"tampered")
    (repaired,) = fetch(ds, build_query(), root=tmp_path)
    assert not repaired.from_cache and repaired.path.read_bytes() == b"original"
    assert state == {"fetches": 2, "closed": 3}
