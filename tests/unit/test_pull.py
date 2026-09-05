from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata.cli import app
from usdata.fetch import ChecksumMismatch
from usdata.manifest import Lockfile, lockfile_path
from usdata.providers.noaa.ghcnd import DATA_URL, SEARCH_URL
from usdata.pull import ManifestChanged, pull, verify

MANIFEST = """
name: okc-precip
sources:
  - dataset: noaa:ghcn-daily
    start: 2024-05-06
    end: 2024-05-07
    variables: [PRCP]
    params: { stations: "USW00013967,USW00003954" }
"""
CSV_V1 = b'"DATE","STATION","PRCP"\n"2024-05-06","USW00013967","10.9"\n'
CSV_V2 = b'"DATE","STATION","PRCP"\n"2024-05-06","USW00013967","99.9"\n'


@pytest.fixture
def manifest(tmp_path: Path) -> Path:
    m = tmp_path / "dataset.yaml"
    m.write_text(MANIFEST)
    return m


def test_pull_resolves_and_writes_lockfile(manifest: Path, tmp_path: Path) -> None:
    with respx.mock() as mock:
        data = mock.get(DATA_URL).mock(return_value=httpx.Response(200, content=CSV_V1))
        result = pull(manifest, root=tmp_path)
    assert data.call_count == 1 and not result.from_lockfile
    lock = Lockfile.load(lockfile_path(manifest))
    assert lock == result.lockfile
    assert lock.manifest == "okc-precip" and len(lock.assets) == 1
    (entry,) = lock.assets
    assert entry.asset.checksum == entry.provenance.checksum
    assert entry.provenance.checksum.startswith("sha256:")
    assert verify(manifest, root=tmp_path) == []


def test_second_pull_restores_from_lockfile_without_resolving(
    manifest: Path, tmp_path: Path
) -> None:
    with respx.mock() as mock:
        mock.get(DATA_URL).mock(return_value=httpx.Response(200, content=CSV_V1))
        first = pull(manifest, root=tmp_path)
    with respx.mock(assert_all_called=False) as mock:
        search = mock.get(SEARCH_URL)
        data = mock.get(DATA_URL)
        again = pull(manifest, root=tmp_path)
    assert again.from_lockfile and not search.called and not data.called
    assert again.fetched[0].from_cache
    assert again.lockfile.generated_at == first.lockfile.generated_at


def test_restore_refetches_missing_file_and_rejects_changed_upstream(
    manifest: Path, tmp_path: Path
) -> None:
    with respx.mock() as mock:
        mock.get(DATA_URL).mock(return_value=httpx.Response(200, content=CSV_V1))
        first = pull(manifest, root=tmp_path)
    path = first.fetched[0].path
    path.unlink()
    assert [d.problem for d in verify(manifest, root=tmp_path)] == ["missing"]
    with respx.mock() as mock:
        mock.get(DATA_URL).mock(return_value=httpx.Response(200, content=CSV_V1))
        restored = pull(manifest, root=tmp_path)
    assert restored.from_lockfile and not restored.fetched[0].from_cache
    assert path.read_bytes() == CSV_V1
    path.unlink()
    with respx.mock() as mock:
        mock.get(DATA_URL).mock(return_value=httpx.Response(200, content=CSV_V2))
        with pytest.raises(ChecksumMismatch):
            pull(manifest, root=tmp_path)
    assert not path.exists()


def test_verify_detects_local_modification(manifest: Path, tmp_path: Path) -> None:
    with respx.mock() as mock:
        mock.get(DATA_URL).mock(return_value=httpx.Response(200, content=CSV_V1))
        result = pull(manifest, root=tmp_path)
    result.fetched[0].path.write_bytes(CSV_V2)
    (drift,) = verify(manifest, root=tmp_path)
    assert drift.problem == "checksum mismatch" and drift.dataset_id == "noaa:ghcn-daily"


def test_edited_manifest_requires_force(manifest: Path, tmp_path: Path) -> None:
    with respx.mock() as mock:
        mock.get(DATA_URL).mock(return_value=httpx.Response(200, content=CSV_V1))
        pull(manifest, root=tmp_path)
    manifest.write_text(MANIFEST.replace("2024-05-07", "2024-05-08"))
    with pytest.raises(ManifestChanged):
        pull(manifest, root=tmp_path)
    with respx.mock() as mock:
        data = mock.get(DATA_URL).mock(return_value=httpx.Response(200, content=CSV_V1))
        forced = pull(manifest, root=tmp_path, force=True)
    assert data.called and not forced.from_lockfile
    saved = Lockfile.load(lockfile_path(manifest))
    assert saved.manifest_checksum == forced.lockfile.manifest_checksum


def test_cli_pull_and_verify_roundtrip(manifest: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    with respx.mock() as mock:
        mock.get(DATA_URL).mock(return_value=httpx.Response(200, content=CSV_V1))
        pulled = runner.invoke(app, ["pull", str(manifest), "--cache-dir", str(tmp_path)])
    assert pulled.exit_code == 0 and "fetched" in pulled.stdout and "wrote" in pulled.output
    ok = runner.invoke(app, ["verify", str(manifest), "--cache-dir", str(tmp_path)])
    assert ok.exit_code == 0
    Path(pulled.stdout.split("\t")[0]).write_bytes(CSV_V2)
    bad = runner.invoke(app, ["verify", str(manifest), "--cache-dir", str(tmp_path)])
    assert bad.exit_code == 1 and "checksum mismatch" in bad.stdout
    with respx.mock() as mock:
        mock.get(DATA_URL).mock(return_value=httpx.Response(200, content=CSV_V2))
        stale = runner.invoke(app, ["pull", str(manifest), "--cache-dir", str(tmp_path)])
    # Restore refetches the altered file; upstream now differs from the lock: exit 4.
    assert stale.exit_code == 4 and "expected sha256" in stale.output
