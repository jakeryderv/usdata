from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata import build_query, get, provenance
from usdata._files import atomic_write_text
from usdata.cache import asset_path, sha256_file
from usdata.cli import app
from usdata.fetch import ChecksumMismatch, fetch, fetch_asset
from usdata.manifest import Lockfile, Manifest, SourceSpec, lockfile_path
from usdata.models import Asset, Protocol
from usdata.providers.noaa.ghcnd import DATA_URL, GhcnDaily
from usdata.pull import pull, verify
from usdata.registry import Registry

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


def test_cached_asset_honors_new_checksum_and_preserves_old_file(tmp_path: Path) -> None:
    ds = get("noaa:ghcn-daily")
    asset = Asset(id="data", dataset_id=ds.id, href=DATA_URL, protocol=Protocol.HTTP)
    with respx.mock() as mock:
        data = mock.get(DATA_URL).respond(200, content=b"original")
        original = fetch_asset(ds, asset, root=tmp_path)
        pinned = asset.model_copy(update={"checksum": "sha256:" + "0" * 64})
        with pytest.raises(ChecksumMismatch):
            fetch_asset(ds, pinned, root=tmp_path)
        assert data.call_count == 2
    assert original.path.read_bytes() == b"original"
    assert provenance.read(original.path) == original.provenance
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.parametrize(
    "dataset_id,asset_id",
    [
        ("noaa:../../outside", "data"),
        ("/tmp:dataset", "data"),
        ("noaa:dataset", ".."),
        ("noaa:dataset", r"..\outside"),
    ],
)
def test_unsafe_cache_components_rejected(tmp_path: Path, dataset_id: str, asset_id: str) -> None:
    asset = Asset(id=asset_id, dataset_id=dataset_id, href=DATA_URL, protocol=Protocol.HTTP)
    with pytest.raises(ValueError, match="unsafe"):
        asset_path(asset, tmp_path)


@pytest.mark.parametrize("link", ["provider", "asset", "sidecar"])
def test_cache_symlink_escape_rejected(tmp_path: Path, link: str) -> None:
    root, outside = tmp_path / "cache", tmp_path / "outside"
    outside.mkdir()
    asset = Asset(id="data", dataset_id="noaa:ghcn-daily", href=DATA_URL, protocol=Protocol.HTTP)
    path = asset_path(asset, root)
    path.parent.mkdir(parents=True)
    if link == "provider":
        path.parent.rmdir()
        path.parent.parent.rmdir()
        (root / "noaa").symlink_to(outside, target_is_directory=True)
    else:
        target = path if link == "asset" else provenance.sidecar_path(path)
        target.symlink_to(outside / "victim")
    with pytest.raises(ValueError, match="escapes root"):
        asset_path(asset, root)
    assert list(outside.iterdir()) == []


def test_failed_atomic_write_keeps_previous_record(tmp_path: Path, monkeypatch) -> None:
    dest = tmp_path / "record.json"
    dest.write_text("original")

    def fail_replace(self, target):
        raise OSError("simulated interruption")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="interruption"):
        atomic_write_text(dest, "replacement")
    assert dest.read_text() == "original"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["record.json"]


@pytest.mark.parametrize("body", [MANIFEST + "    variable: [PRCP]\n", MANIFEST + "typo: true\n"])
def test_manifest_rejects_unknown_fields(tmp_path: Path, body: str) -> None:
    path = tmp_path / "dataset.yaml"
    path.write_text(body)
    with pytest.raises(ValueError, match="Extra inputs"):
        Manifest.load(path)
    result = CliRunner().invoke(app, ["pull", str(path)])
    assert result.exit_code == 2 and "Extra inputs" in result.output


def test_provider_params_remain_supported() -> None:
    source = SourceSpec(dataset="noaa:ghcn-daily", params={"stations": "X", "units": "metric"})
    assert source.to_query().params == {"stations": "X", "units": "metric"}
    with pytest.raises(ValueError, match="reserved"):
        SourceSpec(dataset="noaa:ghcn-daily", params={"start": "2024-01-01"})


@pytest.mark.parametrize(
    "args",
    [
        ["search", "--start", "not-a-date"],
        ["search", "--start", "2025-01-01", "--end", "2024-01-01"],
        [
            "fetch",
            "noaa:nexrad-level2",
            "-p",
            "site=XXXX",
            "--start",
            "2024-05-06",
            "--end",
            "2024-05-07",
        ],
    ],
)
def test_cli_input_errors_are_explained(args: list[str]) -> None:
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2
    assert result.output.strip()


def test_cli_malformed_manifest_and_lockfile(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("name: [")
    result = CliRunner().invoke(app, ["pull", str(manifest)])
    assert result.exit_code == 2 and "invalid manifest YAML" in result.output
    manifest.write_text(MANIFEST)
    lockfile_path(manifest).write_text("{")
    result = CliRunner().invoke(app, ["verify", str(manifest)])
    assert result.exit_code == 2 and result.output.strip()


@pytest.mark.parametrize("fail", [False, True])
def test_fetch_reuses_and_closes_owned_client(tmp_path: Path, monkeypatch, fail: bool) -> None:
    clients: list[httpx.Client] = []
    requests: list[httpx.Request] = []

    def respond(request):
        requests.append(request)
        return httpx.Response(500 if fail else 200, content=b"data")

    def make_client():
        client = httpx.Client(transport=httpx.MockTransport(respond))
        clients.append(client)
        return client

    monkeypatch.setattr("usdata.protocols.http.client", make_client)
    query = build_query(start="2024-01-01", end="2024-01-02", stations=[f"S{i}" for i in range(51)])
    if fail:
        with pytest.raises(httpx.HTTPStatusError):
            fetch(get("noaa:ghcn-daily"), query, root=tmp_path)
    else:
        assert len(fetch(get("noaa:ghcn-daily"), query, root=tmp_path)) == 2
    assert len(requests) == (3 if fail else 2)
    assert len(clients) == 1 and clients[0].is_closed


def test_injected_client_remains_open() -> None:
    with httpx.Client() as client:
        with GhcnDaily(get("noaa:ghcn-daily"), client=client):
            pass
        assert not client.is_closed


def test_registry_infers_multiple_domains() -> None:
    datasets = [get("noaa:ghcn-daily"), get("noaa:nexrad-level2")]
    registry = Registry(datasets)
    assert {domain.id for domain in registry.domains()} == {d.domain for d in datasets}


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
