"""Restore reports every upstream change at once; update rewrites only selected pins."""

from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata.cli import app
from usdata.fetch import ChecksumMismatch
from usdata.manifest import Lockfile, lockfile_path
from usdata.providers.noaa.ghcnd import DATA_URL
from usdata.providers.usgs.daily import ITEMS_URL
from usdata.pull import UnknownAssets, UpstreamChanged, pull, verify

MANIFEST = """
name: drift
sources:
  - dataset: noaa:ghcn-daily
    start: 2024-05-06
    end: 2024-05-07
    params: { stations: USW00013967 }
  - dataset: noaa:ghcn-daily
    start: 2024-05-06
    end: 2024-05-07
    params: { stations: USW00003954 }
  - dataset: usgs:water-daily
    start: 2024-05-06
    end: 2024-05-07
    params: { site: "07164500" }
"""
GHCN = "noaa:ghcn-daily"
USGS = "usgs:water-daily"


def serve(mock: respx.MockRouter, ghcn: dict[str, bytes], usgs: bytes) -> None:
    """Mock both services; GHCN bytes vary by the station in the request."""

    def by_station(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=ghcn[request.url.params["stations"]])

    mock.get(DATA_URL).mock(side_effect=by_station)
    mock.get(ITEMS_URL, params={"f": "json"}).respond(
        200, json={"features": [{"id": "a"}], "links": []}
    )
    mock.get(ITEMS_URL, params={"f": "csv"}).respond(200, content=usgs)


V1 = {"USW00013967": b"a1", "USW00003954": b"b1"}
V2 = {"USW00013967": b"a2", "USW00003954": b"b2"}


@pytest.fixture
def locked(tmp_path: Path) -> tuple[Path, Path]:
    """A manifest pulled once against version 1 of every source, with its cache emptied."""
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    root = tmp_path / "cache"
    with respx.mock() as mock:
        serve(mock, V1, b"u1")
        result = pull(manifest, root=root)
    assert len(result.fetched) == 3
    for item in result.fetched:
        item.path.unlink()
    return manifest, root


def ids(manifest: Path, dataset: str) -> list[str]:
    lock = Lockfile.load(lockfile_path(manifest))
    return [e.asset.id for e in lock.assets if e.asset.dataset_id == dataset]


def test_restore_reports_every_changed_asset_and_keeps_lockfile(
    locked: tuple[Path, Path],
) -> None:
    manifest, root = locked
    before = lockfile_path(manifest).read_bytes()
    with respx.mock(assert_all_called=False) as mock:
        serve(mock, V2, b"u1")
        with pytest.raises(UpstreamChanged) as info:
            pull(manifest, root=root)
    assert isinstance(info.value, ChecksumMismatch)
    assert sorted(d.asset_id for d in info.value.drift) == sorted(ids(manifest, GHCN))
    assert {d.problem for d in info.value.drift} == {"upstream changed"}
    assert all(not d.path.exists() for d in info.value.drift)
    assert lockfile_path(manifest).read_bytes() == before
    # The unchanged USGS asset was still restored.
    assert [d.problem for d in verify(manifest, root=root)] == ["missing", "missing"]


def test_update_by_asset_rewrites_only_that_pin(locked: tuple[Path, Path]) -> None:
    manifest, root = locked
    first, second = ids(manifest, GHCN)
    original = Lockfile.load(lockfile_path(manifest))
    with respx.mock(assert_all_called=False) as mock:
        serve(mock, V2, b"u1")
        with pytest.raises(UpstreamChanged) as info:
            pull(manifest, root=root, update=[first])
    # The other GHCN entry still drifts, so nothing is written.
    assert [d.asset_id for d in info.value.drift] == [second]
    assert Lockfile.load(lockfile_path(manifest)) == original
    with respx.mock(assert_all_called=False) as mock:
        serve(mock, {**V1, "USW00013967": b"a2"}, b"u1")
        result = pull(manifest, root=root, update=[first])
    assert result.updated == [first] and result.from_lockfile
    updated = Lockfile.load(lockfile_path(manifest))
    (changed,) = [e for e in updated.assets if e.asset.id == first]
    kept = [e for e in updated.assets if e.asset.id != first]
    assert changed.asset.checksum == changed.provenance.checksum
    assert changed.provenance.checksum != original.assets[0].provenance.checksum
    assert kept == [e for e in original.assets if e.asset.id != first]
    assert updated.generated_at == original.generated_at
    assert verify(manifest, root=root) == []


def test_update_by_dataset_refreshes_its_entries_and_no_others(
    locked: tuple[Path, Path],
) -> None:
    manifest, root = locked
    original = Lockfile.load(lockfile_path(manifest))
    with respx.mock(assert_all_called=False) as mock:
        serve(mock, V2, b"u1")
        result = pull(manifest, root=root, update=[GHCN])
    assert sorted(result.updated) == sorted(ids(manifest, GHCN))
    updated = Lockfile.load(lockfile_path(manifest))
    usgs_before = [e for e in original.assets if e.asset.dataset_id == USGS]
    usgs_after = [e for e in updated.assets if e.asset.dataset_id == USGS]
    assert usgs_after == usgs_before
    assert verify(manifest, root=root) == []


def test_update_with_unchanged_upstream_leaves_lockfile_identical(
    locked: tuple[Path, Path],
) -> None:
    manifest, root = locked
    before = lockfile_path(manifest).read_bytes()
    with respx.mock(assert_all_called=False) as mock:
        serve(mock, V1, b"u1")
        result = pull(manifest, root=root, update=[GHCN, USGS])
    assert result.updated == [] and not any(f.from_cache for f in result.fetched)
    assert lockfile_path(manifest).read_bytes() == before
    assert verify(manifest, root=root) == []


def test_update_selector_errors(locked: tuple[Path, Path], tmp_path: Path) -> None:
    manifest, root = locked
    with pytest.raises(UnknownAssets, match="nope"), respx.mock(assert_all_called=False):
        pull(manifest, root=root, update=["nope"])
    with pytest.raises(ValueError, match="exclusive"), respx.mock(assert_all_called=False):
        pull(manifest, root=root, force=True, update=[GHCN])
    fresh = tmp_path / "fresh.yaml"
    fresh.write_text(MANIFEST)
    with pytest.raises(ValueError, match="no lockfile"), respx.mock(assert_all_called=False):
        pull(fresh, root=root, update=[GHCN])


def test_cli_reports_drift_then_updates(locked: tuple[Path, Path]) -> None:
    manifest, root = locked
    runner = CliRunner()
    args = [str(manifest), "--cache-dir", str(root)]
    with respx.mock(assert_all_called=False) as mock:
        serve(mock, V2, b"u1")
        failed = runner.invoke(app, ["pull", *args])
    assert failed.exit_code == 4
    assert failed.stdout.count("upstream changed") == 2 and "--update" in failed.output
    with respx.mock(assert_all_called=False) as mock:
        serve(mock, V2, b"u1")
        bad = runner.invoke(app, ["pull", *args, "--update", "nope"])
    assert bad.exit_code == 2 and "nope" in bad.output
    with respx.mock(assert_all_called=False) as mock:
        serve(mock, V2, b"u1")
        ok = runner.invoke(app, ["pull", *args, "--update", GHCN])
    assert ok.exit_code == 0
    assert ok.stdout.count("\tupdated\t") == 2 and ok.stdout.count("\tcached\t") == 1
    assert "updated 2 pin(s)" in ok.output
    assert runner.invoke(app, ["verify", *args]).exit_code == 0
