from pathlib import Path

import pytest
import respx

from usdata import provenance
from usdata.cache import sha256_file
from usdata.fetch import ChecksumMismatch
from usdata.manifest import Lockfile, lockfile_path
from usdata.providers.noaa.ghcnd import DATA_URL
from usdata.pull import pull, verify

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
