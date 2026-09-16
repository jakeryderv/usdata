import importlib
import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata import ChecksumMismatch
from usdata.cli import app
from usdata.manifest import Lockfile, lockfile_path
from usdata.models import Dataset
from usdata.providers.base import Provider, QueryError
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
SECOND_SOURCE = (
    "  - dataset: noaa:ghcn-daily\n    start: 2024-05-06\n    end: 2024-05-07\n"
    "    params: { stations: USW00094728 }\n"
)
NAMED = MANIFEST.replace("  - dataset:", "  - name: okc\n    dataset:") + SECOND_SOURCE.replace(
    "  - dataset:", "  - name: nyc\n    dataset:"
)
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
    assert (
        stale.exit_code == 4 and "upstream changed" in stale.stdout and "--update" in stale.output
    )


def test_verify_rejects_changed_manifest(manifest: Path, tmp_path: Path) -> None:
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(200, content=CSV_V1)
        pull(manifest, root=tmp_path)
    manifest.write_text(MANIFEST.replace("2024-05-07", "2024-05-08"))
    with pytest.raises(ManifestChanged):
        verify(manifest, root=tmp_path)
    result = CliRunner().invoke(app, ["verify", str(manifest), "--cache-dir", str(tmp_path)])
    assert result.exit_code == 2 and "changed" in result.output


@pytest.mark.parametrize("allow_empty", [False, True])
def test_empty_source_is_explicit_and_failed_resolve_preserves_lock(
    manifest: Path, tmp_path: Path, allow_empty: bool
) -> None:
    with respx.mock() as mock:
        mock.get(DATA_URL).respond(200, content=CSV_V1)
        pull(manifest, root=tmp_path)
    original_lock = lockfile_path(manifest).read_bytes()
    manifest.write_text(
        MANIFEST + "  - dataset: noaa:ghcn-daily\n"
        "    location: ok\n    start: 2024-05-06\n    end: 2024-05-07\n"
        f"    allow_empty: {str(allow_empty).lower()}\n"
    )
    with respx.mock() as mock:
        mock.get(SEARCH_URL).respond(200, json={"results": [], "count": 0})
        result = CliRunner().invoke(
            app, ["pull", str(manifest), "--cache-dir", str(tmp_path), "--force"]
        )
    if allow_empty:
        assert result.exit_code == 0
        assert len(Lockfile.load(lockfile_path(manifest)).assets) == 1
        assert verify(manifest, root=tmp_path) == []
    else:
        assert result.exit_code == 1 and "source 2" in result.output
        assert lockfile_path(manifest).read_bytes() == original_lock


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            "  - dataset: noaa:hrrr\n    start: 2024-05-06T20:00Z\n    end: 2024-05-06T20:00Z\n"
            "    params: { cycle: 99, forecast_hour: 0 }\n",
            "cycle must be an integer from 0 to 23",
        ),
        (
            "  - dataset: noaa:ghcn-daily\n    start: 2024-05-06\n    end: 2024-05-07\n"
            "    params: { station: USW00013967 }\n",
            "unsupported noaa:ghcn-daily params: station",
        ),
    ],
    ids=["declared-model", "hand-written"],
)
def test_a_bad_source_fails_before_the_first_one_is_fetched(
    tmp_path: Path, source: str, message: str
) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST + source)
    with respx.mock(assert_all_called=False) as mock:
        data = mock.get(DATA_URL)
        with pytest.raises(QueryError, match=message):
            pull(manifest, root=tmp_path)
    assert not data.called
    assert not lockfile_path(manifest).exists()


def test_empty_initial_pull_does_not_create_lockfile(tmp_path: Path) -> None:
    manifest = tmp_path / "empty.yaml"
    manifest.write_text(
        "name: empty\nsources:\n  - dataset: noaa:ghcn-daily\n"
        "    location: ok\n    start: 2024-05-06\n    end: 2024-05-07\n"
    )
    with respx.mock() as mock:
        mock.get(SEARCH_URL).respond(200, json={"results": [], "count": 0})
        result = CliRunner().invoke(app, ["pull", str(manifest), "--cache-dir", str(tmp_path)])
    assert result.exit_code == 1 and "matched no assets" in result.output
    assert not lockfile_path(manifest).exists()


def _counting_adapters(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], list[str]]:
    """Record the dataset of every adapter resolve opens, and of every one it closes."""
    # usdata.pull names both a module and a re-exported function; import the module.
    module = importlib.import_module("usdata.pull")
    real = module.load_adapter
    opened: list[str] = []
    closed: list[str] = []

    def counting(dataset: Dataset) -> Provider:
        adapter = real(dataset)
        opened.append(dataset.id)
        release = adapter.close

        def close() -> None:
            closed.append(dataset.id)
            release()

        monkeypatch.setattr(adapter, "close", close)
        return adapter

    monkeypatch.setattr(module, "load_adapter", counting)
    return opened, closed


def test_resolve_shares_one_adapter_across_sources_on_a_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST + SECOND_SOURCE)
    opened, closed = _counting_adapters(monkeypatch)
    with respx.mock() as mock:
        mock.get(DATA_URL).mock(return_value=httpx.Response(200, content=CSV_V1))
        result = pull(manifest, root=tmp_path)
    assert len(result.fetched) == 2
    assert opened == ["noaa:ghcn-daily"] and closed == ["noaa:ghcn-daily"]


def test_resolve_closes_the_shared_adapter_when_a_later_source_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST + SECOND_SOURCE)
    opened, closed = _counting_adapters(monkeypatch)
    with respx.mock() as mock:
        mock.get(DATA_URL).mock(
            side_effect=[httpx.Response(200, content=CSV_V1), httpx.Response(404)]
        )
        with pytest.raises(httpx.HTTPStatusError):
            pull(manifest, root=tmp_path)
    assert opened == ["noaa:ghcn-daily"] and closed == ["noaa:ghcn-daily"]
    assert not lockfile_path(manifest).exists()


def test_named_sources_group_the_result_and_the_lockfile(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(NAMED)
    with respx.mock() as mock:
        mock.get(DATA_URL).mock(return_value=httpx.Response(200, content=CSV_V1))
        first = pull(manifest, root=tmp_path)
    assert [entry.source for entry in first.lockfile.assets] == ["okc", "nyc"]
    assert list(first.by_source) == ["okc", "nyc"]
    assert first.by_source["okc"] == first.fetched[:1]
    assert first.by_source["nyc"] == first.fetched[1:]
    with respx.mock(assert_all_called=False) as mock:
        data = mock.get(DATA_URL)
        restored = pull(manifest, root=tmp_path)
    assert restored.from_lockfile and not data.called
    assert list(restored.by_source) == ["okc", "nyc"]
    assert [f.asset.id for f in restored.by_source["nyc"]] == [
        f.asset.id for f in first.by_source["nyc"]
    ]


def test_a_lockfile_without_source_keys_groups_by_dataset(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST + SECOND_SOURCE)
    with respx.mock() as mock:
        mock.get(DATA_URL).mock(return_value=httpx.Response(200, content=CSV_V1))
        first = pull(manifest, root=tmp_path)
    assert list(first.by_source) == ["1", "2"]
    lock_path = lockfile_path(manifest)
    written = json.loads(lock_path.read_text())
    for entry in written["assets"]:
        del entry["source"]  # A lockfile from before sources carried keys.
    lock_path.write_text(json.dumps(written))
    assert [entry.source for entry in Lockfile.load(lock_path).assets] == [None, None]
    with respx.mock(assert_all_called=False) as mock:
        data = mock.get(DATA_URL)
        restored = pull(manifest, root=tmp_path)
    assert restored.from_lockfile and not data.called
    # Both sources read the same dataset, so the fallback cannot tell them apart;
    # naming them and pulling with force rewrites the keys.
    assert list(restored.by_source) == ["1"]
    assert restored.by_source["1"] == restored.fetched
