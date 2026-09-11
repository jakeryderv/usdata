"""Preserve the one existing documentation snapshot as offline static assets."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "web/archive/0.10.0.zip"
DIGEST = "7a384842e5a5b228d64a78d36096f56ef03e655d3aabd6777b9f95c5c0025158"
BANNER = (
    '<aside style="padding:12px 20px;background:#18342b;color:#f1f4ee;font:14px sans-serif">'
    "Archived documentation for usdata 0.10.0. "
    '<a style="color:#a8e0bd" href="https://usdata.dev/start/">Read current documentation</a>'
    "</aside>"
)


def install_archive(site: Path, archive_path: Path = ARCHIVE, digest: str = DIGEST) -> None:
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != digest:
        raise ValueError("archived documentation checksum mismatch")
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or not {"index.html", "404.html"} <= set(names):
            raise ValueError("incomplete or duplicate archive paths")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                raise ValueError("unsafe archive path")
        for name in names:
            body = archive.read(name)
            if name.endswith(".html"):
                text = body.decode()
                # The original theme sets body attributes, so find the end of its opening tag.
                end = text.index(">", text.index("<body")) + 1
                body = (text[:end] + BANNER + text[end:]).encode()
            target = site / "0.10.0" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
    # Compatibility endpoint only: it describes the frozen archive, not current main docs.
    (site / "versions.json").write_text(
        json.dumps({"current": "0.10.0", "versions": ["0.10.0"], "archived": True})
    )
