from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from usdata import provenance
from usdata.cache import asset_path, sha256_file
from usdata.cache_ops import (
    candidates,
    entries,
    parse_duration,
    pinned_paths,
    prune,
    total_size,
)
from usdata.cli import app
from usdata.manifest import LockedAsset, Lockfile, lockfile_path
from usdata.models import Asset, Protocol, Provenance

runner = CliRunner()
NOW = datetime(2025, 1, 30, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def temp_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Never read or delete the developer's real cache."""
    root = tmp_path / "cache" / "usdata"
    monkeypatch.setenv("USDATA_CACHE_DIR", str(root))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    return root


def make_asset(dataset_id: str, asset_id: str, body: bytes) -> Asset:
    return Asset(
        id=asset_id,
        dataset_id=dataset_id,
        href=f"https://example.test/{asset_id}",
        protocol=Protocol.HTTP,
        size=len(body),
    )


def cache_file(
    root: Path,
    dataset_id: str,
    asset_id: str,
    *,
    body: bytes = b"bytes",
    retrieved_at: datetime | None = None,
    sidecar: bool = True,
) -> Path:
    """Write one cached file, with the provenance sidecar the core would write."""
    asset = make_asset(dataset_id, asset_id, body)
    path = asset_path(asset, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    if sidecar:
        provenance.write(record(asset, path, retrieved_at or NOW), path)
    return path


def record(asset: Asset, path: Path, retrieved_at: datetime) -> Provenance:
    return Provenance(
        dataset_id=asset.dataset_id,
        provider=asset.dataset_id.partition(":")[0],
        source_url=asset.href,
        retrieved_at=retrieved_at,
        checksum=sha256_file(path),
        size=path.stat().st_size,
        usdata_version="0.0.0",
    )


def write_manifest_lock(directory: Path, root: Path, assets: list[Asset]) -> Path:
    """A manifest and the lockfile beside it that pins ``assets``."""
    manifest = directory / "inputs.yaml"
    manifest.write_text("name: test\nsources:\n  - dataset: noaa:ghcn-daily\n")
    lock = Lockfile(
        manifest=manifest.name,
        manifest_checksum=sha256_file(manifest),
        generated_at=NOW,
        usdata_version="0.0.0",
        assets=[
            LockedAsset(asset=a, provenance=record(a, asset_path(a, root), NOW)) for a in assets
        ],
    )
    lock.save(lockfile_path(manifest))
    return manifest


@pytest.mark.parametrize(
    "text, expected",
    [
        ("30d", timedelta(days=30)),
        ("12h", timedelta(hours=12)),
        (" 7d ", timedelta(days=7)),
        ("P30D", timedelta(days=30)),
        ("P1W", timedelta(weeks=1)),
        ("PT90M", timedelta(minutes=90)),
        ("P1DT6H30M", timedelta(days=1, hours=6, minutes=30)),
    ],
)
def test_parse_duration_accepts_short_and_iso_forms(text: str, expected: timedelta) -> None:
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text", ["", "30", "30 days", "1y", "P1Y", "0d", "-3d", "PT0S"])
def test_parse_duration_rejects_ambiguous_or_empty(text: str) -> None:
    with pytest.raises(ValueError):
        parse_duration(text)


def test_entries_pair_data_files_with_sidecars(temp_cache: Path) -> None:
    cache_file(temp_cache, "noaa:ghcn-daily", "b.csv", body=b"12345", retrieved_at=NOW)
    cache_file(temp_cache, "noaa:ghcn-daily", "a.csv", sidecar=False, body=b"ab")
    cache_file(temp_cache, "usgs:nwis-daily", "c.csv", retrieved_at=NOW)

    found = entries(temp_cache)

    assert [(e.dataset_id, e.asset_id) for e in found] == [
        ("noaa:ghcn-daily", "a.csv"),
        ("noaa:ghcn-daily", "b.csv"),
        ("usgs:nwis-daily", "c.csv"),
    ]
    unrecorded, recorded = found[0], found[1]
    assert unrecorded.retrieved_at is None and not unrecorded.recorded
    assert recorded.recorded and recorded.retrieved_at == NOW
    assert recorded.size == 5
    assert recorded.path.read_bytes() == b"12345"


def test_entries_skip_temporary_files_and_staging(temp_cache: Path) -> None:
    kept = cache_file(temp_cache, "noaa:ghcn-daily", "a.csv", retrieved_at=NOW)
    # What a killed download or sidecar write leaves beside the files it was replacing.
    (kept.parent / ".a.csv.x1y2.part").write_bytes(b"half")
    (kept.parent / ".a.csv.provenance.json.x1y2.part").write_text("{")
    staged = temp_cache / ".staging" / "tmp123" / "noaa" / "ghcn-daily"
    staged.mkdir(parents=True)
    (staged / "b.csv").write_bytes(b"staged")

    assert [entry.path for entry in entries(temp_cache)] == [kept]
    assert total_size(temp_cache) == kept.stat().st_size
    removed = prune(temp_cache, older_than=timedelta(0), now=NOW + timedelta(days=1))
    assert [entry.path for entry in removed] == [kept]
    assert (kept.parent / ".a.csv.x1y2.part").exists(), "a concurrent pull may still own it"


def test_a_naive_retrieval_time_is_read_as_utc_and_ages(temp_cache: Path) -> None:
    path = cache_file(temp_cache, "noaa:ghcn-daily", "a.csv")
    sidecar = provenance.sidecar_path(path)
    data = json.loads(sidecar.read_text())
    data["retrieved_at"] = "2025-01-01T12:00:00"  # as an older or hand-written sidecar has it
    sidecar.write_text(json.dumps(data))
    naive = Provenance.model_validate({**data, "retrieved_at": datetime(2025, 1, 1, 12)})
    assert naive.retrieved_at == datetime(2025, 1, 1, 12, tzinfo=UTC)

    [entry] = entries(temp_cache)
    assert entry.retrieved_at == naive.retrieved_at and entry.age(NOW) == timedelta(days=29)
    assert candidates(temp_cache, older_than=timedelta(days=20), now=NOW) == [entry]
    assert candidates(temp_cache, older_than=timedelta(days=20), now=NOW.replace(tzinfo=None))


def test_entries_is_empty_without_a_cache_directory(temp_cache: Path) -> None:
    assert entries(temp_cache) == [] and total_size(temp_cache) == 0


def test_total_size_counts_data_files_only(temp_cache: Path) -> None:
    cache_file(temp_cache, "noaa:ghcn-daily", "a.csv", body=b"1234")
    cache_file(temp_cache, "noaa:ghcn-daily", "b.csv", body=b"123456")
    assert total_size(temp_cache) == 10


def test_unrecorded_file_ages_from_its_mtime(temp_cache: Path) -> None:
    path = cache_file(temp_cache, "noaa:ghcn-daily", "a.csv", sidecar=False)
    old = (NOW - timedelta(days=10)).timestamp()
    os.utime(path, (old, old))
    [entry] = entries(temp_cache)
    assert entry.age(NOW) == timedelta(days=10)
    assert candidates(temp_cache, older_than=timedelta(days=5), now=NOW) == [entry]
    assert candidates(temp_cache, older_than=timedelta(days=30), now=NOW) == []


def test_prune_removes_old_files_with_their_sidecars(temp_cache: Path) -> None:
    old = cache_file(
        temp_cache, "noaa:ghcn-daily", "old.csv", retrieved_at=NOW - timedelta(days=60)
    )
    fresh = cache_file(temp_cache, "noaa:ghcn-daily", "new.csv", retrieved_at=NOW)

    removed = prune(temp_cache, older_than=timedelta(days=30), now=NOW)

    assert [entry.path for entry in removed] == [old]
    assert not old.exists() and not provenance.sidecar_path(old).exists()
    assert fresh.exists() and provenance.sidecar_path(fresh).exists()


def test_prune_by_dataset_leaves_other_datasets(temp_cache: Path) -> None:
    kept = cache_file(temp_cache, "usgs:nwis-daily", "a.csv", retrieved_at=NOW - timedelta(days=60))
    gone = cache_file(temp_cache, "noaa:ghcn-daily", "a.csv", retrieved_at=NOW - timedelta(days=60))

    removed = prune(temp_cache, dataset="noaa:ghcn-daily", now=NOW)

    assert [entry.path for entry in removed] == [gone]
    assert kept.exists() and not gone.exists()


def test_prune_dry_run_deletes_nothing(temp_cache: Path) -> None:
    path = cache_file(temp_cache, "noaa:ghcn-daily", "a.csv", retrieved_at=NOW - timedelta(days=60))

    removed = prune(temp_cache, older_than=timedelta(days=30), dry_run=True, now=NOW)

    assert [entry.path for entry in removed] == [path]
    assert path.exists() and provenance.sidecar_path(path).exists()


def test_prune_never_touches_pinned_paths(temp_cache: Path) -> None:
    pinned = cache_file(
        temp_cache, "noaa:ghcn-daily", "a.csv", retrieved_at=NOW - timedelta(days=60)
    )
    loose = cache_file(
        temp_cache, "noaa:ghcn-daily", "b.csv", retrieved_at=NOW - timedelta(days=60)
    )

    removed = prune(temp_cache, older_than=timedelta(days=30), pinned=frozenset({pinned}), now=NOW)

    assert [entry.path for entry in removed] == [loose]
    assert pinned.exists() and provenance.sidecar_path(pinned).exists()


def test_pinned_paths_reads_lockfiles_beside_manifests(tmp_path: Path, temp_cache: Path) -> None:
    asset = make_asset("noaa:ghcn-daily", "a.csv", b"bytes")
    cache_file(temp_cache, "noaa:ghcn-daily", "a.csv")
    project = tmp_path / "project"
    project.mkdir()
    write_manifest_lock(project, temp_cache, [asset])

    assert pinned_paths(project, temp_cache) == {asset_path(asset, temp_cache)}


def test_pinned_paths_ignores_manifests_without_a_lockfile(
    tmp_path: Path, temp_cache: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "inputs.yaml").write_text("name: test\nsources:\n  - dataset: noaa:ghcn-daily\n")
    assert pinned_paths(project, temp_cache) == set()


def test_pinned_paths_refuses_an_unreadable_lockfile(tmp_path: Path, temp_cache: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    manifest = project / "inputs.yaml"
    manifest.write_text("name: test\nsources:\n  - dataset: noaa:ghcn-daily\n")
    lockfile_path(manifest).write_text("{")
    with pytest.raises(ValueError, match="cannot read lockfile"):
        pinned_paths(project, temp_cache)


def test_cli_path_prints_the_cache_directory(temp_cache: Path) -> None:
    result = runner.invoke(app, ["cache", "path"])
    assert result.exit_code == 0
    assert result.stdout.strip() == str(temp_cache)


def test_cli_list_shows_size_and_retrieval_time(temp_cache: Path) -> None:
    cache_file(temp_cache, "noaa:ghcn-daily", "a.csv", retrieved_at=NOW)
    cache_file(temp_cache, "noaa:ghcn-daily", "b.csv", sidecar=False)

    result = runner.invoke(app, ["cache", "list"])

    assert result.exit_code == 0
    assert "noaa:ghcn-daily" in result.output and NOW.isoformat() in result.output
    assert "unrecorded" in result.output
    assert "2 file(s)" in result.output


def test_cli_list_json_is_machine_readable(temp_cache: Path) -> None:
    cache_file(temp_cache, "noaa:ghcn-daily", "a.csv", body=b"1234", retrieved_at=NOW)

    result = runner.invoke(app, ["cache", "list", "--json"])

    assert result.exit_code == 0
    [entry] = json.loads(result.stdout)
    assert entry["dataset_id"] == "noaa:ghcn-daily"
    assert entry["asset_id"] == "a.csv"
    assert entry["size"] == 4
    assert entry["retrieved_at"].startswith("2025-01-30T12:00:00")


def test_cli_list_without_matches_exits_1(temp_cache: Path) -> None:
    empty = runner.invoke(app, ["cache", "list"])
    assert empty.exit_code == 1 and "No cached files." in empty.output
    cache_file(temp_cache, "noaa:ghcn-daily", "a.csv")
    missing = runner.invoke(app, ["cache", "list", "--dataset", "usgs:nwis-daily"])
    assert missing.exit_code == 1 and "usgs:nwis-daily" in missing.output


def test_cli_size_reports_bytes_and_location(temp_cache: Path) -> None:
    cache_file(temp_cache, "noaa:ghcn-daily", "a.csv", body=b"1234")
    result = runner.invoke(app, ["cache", "size"])
    assert result.exit_code == 0
    assert "4 bytes" in result.stdout and str(temp_cache) in result.stdout


def test_cli_prune_needs_a_filter(temp_cache: Path) -> None:
    result = runner.invoke(app, ["cache", "prune"])
    assert result.exit_code == 2 and "--older-than" in result.output


def test_cli_prune_rejects_an_unparsable_age(temp_cache: Path) -> None:
    result = runner.invoke(app, ["cache", "prune", "--older-than", "one month"])
    assert result.exit_code == 2 and "invalid duration" in result.output


def test_cli_prune_dry_run_lists_without_deleting(temp_cache: Path) -> None:
    path = cache_file(temp_cache, "noaa:ghcn-daily", "a.csv", retrieved_at=NOW - timedelta(days=60))

    result = runner.invoke(app, ["cache", "prune", "--older-than", "30d", "--dry-run"])

    assert result.exit_code == 0
    assert str(path) in result.output and "would remove 1 file(s)" in result.output
    assert path.exists()


def test_cli_prune_keeps_pinned_files_unless_asked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, temp_cache: Path
) -> None:
    asset = make_asset("noaa:ghcn-daily", "a.csv", b"bytes")
    pinned = cache_file(
        temp_cache, "noaa:ghcn-daily", "a.csv", retrieved_at=NOW - timedelta(days=60)
    )
    loose = cache_file(
        temp_cache, "noaa:ghcn-daily", "b.csv", retrieved_at=NOW - timedelta(days=60)
    )
    project = tmp_path / "project"
    project.mkdir()
    write_manifest_lock(project, temp_cache, [asset])
    monkeypatch.chdir(project)

    kept = runner.invoke(app, ["cache", "prune", "--older-than", "30d"])
    assert kept.exit_code == 0
    assert "removed 1 file(s)" in kept.output and "kept 1 pinned file(s)" in kept.output
    assert pinned.exists() and not loose.exists()

    everything = runner.invoke(app, ["cache", "prune", "--older-than", "30d", "--include-pinned"])
    assert everything.exit_code == 0 and "removed 1 file(s)" in everything.output
    assert not pinned.exists() and not provenance.sidecar_path(pinned).exists()
