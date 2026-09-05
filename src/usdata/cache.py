"""Local file cache. Layout: ``<cache_dir>/<provider>/<dataset name>/<asset id>``."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from usdata.models import Asset

ENV_VAR = "USDATA_CACHE_DIR"


def cache_dir() -> Path:
    """Cache root: $USDATA_CACHE_DIR, else $XDG_CACHE_HOME/usdata, else ~/.cache/usdata."""
    if override := os.environ.get(ENV_VAR):
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "usdata"


def asset_path(asset: Asset, root: Path | None = None) -> Path:
    """Where an asset lives in the cache: <root>/<provider>/<dataset>/<asset id>."""
    provider, sep, name = asset.dataset_id.partition(":")
    if not sep or any(
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", part) for part in (provider, name)
    ):
        raise ValueError(f"unsafe dataset id: {asset.dataset_id!r}")
    safe_id = asset.id.replace("/", "_")
    if not safe_id or safe_id in {".", ".."} or "\\" in safe_id or "\x00" in safe_id:
        raise ValueError(f"unsafe asset id: {asset.id!r}")
    base = (root or cache_dir()).expanduser().resolve()
    path = base / provider / name / safe_id
    for candidate in (path, path.with_name(path.name + ".provenance.json")):
        if not candidate.resolve().is_relative_to(base):
            raise ValueError(f"cache path escapes root: {candidate}")
    return path


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Hex sha256 of a file, prefixed 'sha256:' to match Asset.checksum."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"
