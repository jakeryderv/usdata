"""Local file cache. Layout: ``<cache_dir>/<provider>/<dataset name>/<asset id>``."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from usdata.models import Asset

ENV_VAR = "USDATA_CACHE_DIR"


def cache_dir() -> Path:
    if override := os.environ.get(ENV_VAR):
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "usdata"


def asset_path(asset: Asset, root: Path | None = None) -> Path:
    provider, name = asset.dataset_id.split(":", 1)
    safe_id = asset.id.replace("/", "_")
    return (root or cache_dir()) / provider / name / safe_id


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"
