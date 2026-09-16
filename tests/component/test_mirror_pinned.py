"""The mirror upload and prune script: content addressing, HEAD before PUT, and a set difference."""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

import httpx
import pytest
import respx

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = "https://data.example.test"


@pytest.fixture
def script(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("mirror_pinned")


def pinned(root: Path, slug: str, files: dict[str, bytes], cache: Path) -> Path:
    """A pinned manifest and lockfile over ``files`` (asset id -> bytes), with the bytes cached."""
    example = root / "examples" / slug
    example.mkdir(parents=True)
    manifest = example / "dataset.yaml"
    manifest.write_text(f"name: {slug}\nsources:\n  - dataset: noaa:mrms\n")
    assets = []
    for asset_id, data in files.items():
        checksum = "sha256:" + hashlib.sha256(data).hexdigest()
        path = cache / "noaa" / "mrms" / asset_id
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        assets.append(
            {
                "asset": {
                    "id": asset_id,
                    "dataset_id": "noaa:mrms",
                    "media_type": "application/x-grib2",
                },
                "provenance": {"checksum": checksum, "size": len(data)},
            }
        )
    manifest.with_suffix(".lock.json").write_text(
        json.dumps({"manifest": slug, "manifest_checksum": "sha256:0", "assets": assets})
    )
    return manifest


def test_upload_sends_only_what_the_mirror_lacks_and_never_a_wrong_file(script, tmp_path):
    cache = tmp_path / "cache"
    first = pinned(tmp_path, "one", {"a.grib2": b"aaa", "b.grib2": b"bbb"}, cache)
    second = pinned(tmp_path, "two", {"c.grib2": b"aaa"}, cache)  # same bytes as a.grib2
    objects = script.pinned_objects([first, second])
    assert len(objects) == 2, "identical bytes share one key"
    from usdata.mirror import object_key, object_url

    sha_a = "sha256:" + hashlib.sha256(b"aaa").hexdigest()
    sha_b = "sha256:" + hashlib.sha256(b"bbb").hexdigest()
    commands: list[list[str]] = []
    with respx.mock() as mock:
        mock.head(object_url(PUBLIC, sha_a)).respond(200)
        mock.head(object_url(PUBLIC, sha_b)).respond(404)
        uploaded = script.upload(
            [first, second],
            cache,
            public_url=PUBLIC,
            bucket="b",
            run=lambda c: commands.append(c) or "",
        )
    assert uploaded == [sha_b]
    (command,) = commands
    assert command[:3] == ["aws", "s3api", "put-object"]
    assert command[command.index("--key") + 1] == object_key(sha_b)
    assert command[command.index("--body") + 1] == str(cache / "noaa/mrms/b.grib2")
    assert command[command.index("--content-type") + 1] == "application/x-grib2"
    assert "immutable" in command[command.index("--cache-control") + 1]

    # Dry run plans without sending; a cache file that no longer matches its pin is refused.
    commands.clear()
    with respx.mock() as mock:
        mock.head(object_url(PUBLIC, sha_a)).respond(200)
        mock.head(object_url(PUBLIC, sha_b)).respond(404)
        assert (
            script.upload([first], cache, public_url=PUBLIC, dry_run=True, run=commands.append)
            == []
        )
        (cache / "noaa/mrms/b.grib2").write_bytes(b"changed")
        with pytest.raises(ValueError, match="not the pinned"):
            script.upload([first], cache, public_url=PUBLIC, run=commands.append)
    assert commands == []
    with respx.mock() as mock, pytest.raises(httpx.HTTPStatusError):
        mock.head(object_url(PUBLIC, sha_a)).respond(500)
        script.upload([second], cache, public_url=PUBLIC, run=commands.append)
    with respx.mock() as mock, pytest.raises(FileNotFoundError, match="restore it first"):
        mock.head(object_url(PUBLIC, sha_a)).respond(404)
        script.upload([second], tmp_path / "empty", public_url=PUBLIC, run=commands.append)


def test_prune_deletes_only_unreferenced_keys_and_only_when_told(script, tmp_path):
    cache = tmp_path / "cache"
    manifest = pinned(tmp_path, "one", {"a.grib2": b"aaa"}, cache)
    from usdata.mirror import object_key

    kept = object_key("sha256:" + hashlib.sha256(b"aaa").hexdigest())
    stray = "sha256/" + "ff" * 32
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> str:
        commands.append(command)
        return json.dumps([stray, kept]) if command[2] == "list-objects-v2" else ""

    assert script.prune([manifest], bucket="b", run=fake_run) == [stray]
    assert [c[2] for c in commands] == ["list-objects-v2"]
    assert script.prune([manifest], bucket="b", delete=True, run=fake_run) == [stray]
    assert commands[-1] == ["aws", "s3api", "delete-object", "--bucket", "b", "--key", stray]
    assert script.list_keys("b", lambda c: "null") == []
