"""The committed example lockfiles: offline validation, discovery, and the restore runner."""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def scripts(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return {
        name: importlib.import_module(name) for name in ("check_notebooks", "restore_lockfiles")
    }


def write_pinned_example(root: Path, slug: str, *, lockfile: bool = True) -> Path:
    """A catalog naming ``slug`` as pinned, its manifest, and a consistent lockfile."""
    example = root / "examples" / slug
    example.mkdir(parents=True, exist_ok=True)
    catalog = root / "examples/catalog.json"
    entries = json.loads(catalog.read_text()) if catalog.exists() else []
    entries.append({"slug": slug, "title": "Q?", "summary": "A.", "pinned": True})
    catalog.write_text(json.dumps(entries))
    manifest = example / "dataset.yaml"
    manifest.write_text(f"name: {slug}\nsources:\n  - dataset: noaa:mrms\n")
    if lockfile:
        digest = "sha256:" + hashlib.sha256(manifest.read_bytes()).hexdigest()
        checksum = "sha256:" + "ab" * 32
        manifest.with_suffix(".lock.json").write_text(
            json.dumps(
                {
                    "manifest": slug,
                    "manifest_checksum": digest,
                    "assets": [
                        {
                            "asset": {"id": "a.grib2", "checksum": checksum},
                            "provenance": {"checksum": checksum, "size": 12},
                        }
                    ],
                }
            )
        )
    return manifest


def test_committed_lockfiles_match_their_manifests(scripts):
    check = scripts["check_notebooks"]
    pinned = check.pinned_manifests()
    assert {m.parent.name for m in pinned} == {
        "goes-imagery",
        "goes-mesoscale",
        "glm-flashes",
        "hrrr-environment",
        "mrms-rotation",
        "gfs-environment",
        "radar-products",
    }
    assert [error for manifest in pinned for error in check.check_lockfile(manifest)] == []
    unpinned = {m.parent.name for m in (ROOT / "examples").glob("*/dataset.yaml")} - {
        m.parent.name for m in pinned
    }
    assert unpinned, "some examples must stay unpinned"


def test_lockfile_check_names_each_way_a_pin_can_be_stale(scripts, tmp_path):
    check = scripts["check_notebooks"]
    manifest = write_pinned_example(tmp_path, "pinned")
    assert check.pinned_manifests(tmp_path) == [manifest]
    assert check.check_lockfile(manifest) == []

    lock = manifest.with_suffix(".lock.json")
    data = json.loads(lock.read_text())
    manifest.write_text(manifest.read_text() + "    allow_empty: true\n")
    assert any("manifest changed" in e for e in check.check_lockfile(manifest))
    lock.write_text(json.dumps({**data, "manifest_checksum": "x", "assets": []}))
    errors = check.check_lockfile(manifest)
    assert any("pins no assets" in e for e in errors) and any(
        "manifest changed" in e for e in errors
    )
    data["assets"][0]["provenance"]["checksum"] = "md5:0"
    lock.write_text(json.dumps(data))
    assert any("no sha256 pinned" in e for e in check.check_lockfile(manifest))
    data["assets"][0]["provenance"]["checksum"] = "sha256:" + "cd" * 32
    lock.write_text(json.dumps(data))
    assert any("checksums differ" in e for e in check.check_lockfile(manifest))
    lock.write_text("{not json")
    assert any("cannot read lockfile" in e for e in check.check_lockfile(manifest))
    lock.unlink()
    assert any("no committed lockfile" in e for e in check.check_lockfile(manifest))
    assert check.check_lockfile(tmp_path / "examples/none/dataset.yaml") == [
        f"{tmp_path / 'examples/none/dataset.yaml'}: pinned example has no manifest"
    ]
    assert check.pinned_manifests(tmp_path / "nowhere") == []


def test_restore_runner_reports_drift_and_failures_without_stopping(scripts, tmp_path, capsys):
    restore = scripts["restore_lockfiles"]
    first = write_pinned_example(tmp_path, "first")
    second = write_pinned_example(tmp_path, "second")
    third = write_pinned_example(tmp_path, "third")
    caches: list[Path] = []

    def fake_restore(manifest: Path, cache: Path) -> list[dict[str, str]]:
        caches.append(cache)
        if manifest == second:
            return [{"asset_id": "a.grib2", "problem": "upstream changed"}]
        if manifest == third:
            raise RuntimeError("bucket unreachable")
        return []

    reports = tmp_path / "reports"
    failures = restore.restore_examples([first, second, third], reports, restore=fake_restore)
    assert len(failures) == 2
    assert "second/dataset.yaml: 1 asset(s) drifted: a.grib2 (upstream changed)" in failures[0]
    assert "bucket unreachable" in failures[1]
    assert len(set(caches)) == 3 and not any(cache.exists() for cache in caches)
    summary = json.loads((reports / "summary.json").read_text())
    assert [r["status"] for r in summary] == ["restored", "drifted", "failed"]
    assert summary[0]["assets"] == 1 and summary[0]["bytes"] == 12
    assert summary[1]["drift"] == [{"asset_id": "a.grib2", "problem": "upstream changed"}]
    assert summary[2]["error"] == "2-error.txt"
    assert "bucket unreachable" in (reports / "2-error.txt").read_text()
    assert "Restoring" in capsys.readouterr().out

    assert restore.resolve_manifests(
        ["second", "examples/first/dataset.yaml"], [first, second], root=tmp_path
    ) == [first, second]
    with pytest.raises(ValueError, match="not a pinned example: nope; choose from: first, second"):
        restore.resolve_manifests(["nope"], [first, second], root=tmp_path)


def test_restore_runner_treats_upstream_drift_as_a_result(scripts, tmp_path, monkeypatch):
    restore = scripts["restore_lockfiles"]
    pull = importlib.import_module("usdata.pull")
    drift = pull.Drift(
        asset_id="a", dataset_id="noaa:mrms", path=tmp_path / "a", problem="upstream changed"
    )

    def raising(manifest, *, root):
        raise pull.UpstreamChanged([drift])

    monkeypatch.setattr(pull, "restore", raising)
    monkeypatch.setattr(pull, "verify", lambda manifest, *, root: [])
    assert restore.restore_pinned(tmp_path / "m.yaml", tmp_path / "cache") == [
        {"asset_id": "a", "problem": "upstream changed"}
    ]
    monkeypatch.setattr(pull, "restore", lambda manifest, *, root: SimpleNamespace(mirrored=[]))
    monkeypatch.setattr(
        pull, "verify", lambda manifest, *, root: [drift.model_copy(update={"problem": "missing"})]
    )
    assert restore.restore_pinned(tmp_path / "m.yaml", tmp_path / "cache") == [
        {"asset_id": "a", "problem": "missing"}
    ]
    # A mirror that stepped in is still drift for this job: the source no longer serves the pin.
    monkeypatch.setattr(pull, "restore", lambda manifest, *, root: SimpleNamespace(mirrored=["b"]))
    monkeypatch.setattr(pull, "verify", lambda manifest, *, root: [])
    assert restore.restore_pinned(tmp_path / "m.yaml", tmp_path / "cache") == [
        {"asset_id": "b", "problem": "upstream changed; restored from the mirror"}
    ]


def test_restore_runner_keeps_a_named_cache_for_the_upload(scripts, tmp_path):
    restore = scripts["restore_lockfiles"]
    manifest = write_pinned_example(tmp_path, "kept")
    caches: list[Path] = []
    keep = tmp_path / "keep"
    assert not restore.restore_examples(
        [manifest], tmp_path / "reports", cache=keep, restore=lambda m, c: caches.append(c) or []
    )
    assert caches == [keep]
