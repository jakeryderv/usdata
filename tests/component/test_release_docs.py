import base64
import gzip
import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("release_docs", ROOT / "scripts/release_docs.py")
assert spec and spec.loader
release_docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_docs)


def test_release_archives_preserve_bytes_and_source_identity(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    for name, data in {
        "index.html": b"<h1>Start</h1>",
        "404.html": b"Missing",
        "image.png": bytes(range(256)),
    }.items():
        (site / name).write_bytes(data)
    output = tmp_path / "archives"
    descriptor = release_docs.package_site(site, output, "0.10.0", "a" * 40, "b" * 40)
    info = json.loads(descriptor.read_text())
    assert info["package_commit"] == "a" * 40
    assert info["docs_commit"] == "b" * 40
    bundle = (output / info["bundle"]["name"]).read_bytes()
    assert hashlib.sha256(bundle).hexdigest() == info["bundle"]["sha256"]
    assert len(bundle) == info["bundle"]["size"]
    records = [json.loads(line) for line in gzip.decompress(bundle).splitlines()]
    with zipfile.ZipFile(next(output.glob("*.zip"))) as archive:
        for record in records:
            data = base64.b64decode(record["data"])
            assert data == (site / record["path"]).read_bytes() == archive.read(record["path"])
            assert hashlib.sha256(data).hexdigest() == record["sha256"]


def test_incomplete_site_never_gets_a_ready_descriptor(tmp_path):
    (tmp_path / "index.html").write_text("incomplete")
    output = tmp_path / "output"
    with pytest.raises(ValueError, match=r"404\.html"):
        release_docs.package_site(tmp_path, output, "0.10.0", "a" * 40, "b" * 40)
    assert not output.exists()
