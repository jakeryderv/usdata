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
    return cached_path(asset.dataset_id, asset.id, root)


def cached_path(dataset_id: str, asset_id: str, root: Path | None = None) -> Path:
    """Where the cache keeps one asset, addressed by its ids rather than the asset itself.

    Args:
        dataset_id: The owning dataset's ``provider:name`` id.
        asset_id: The asset's id; slashes become underscores, as they do on fetch.
        root: Cache root to resolve against, or the configured cache directory.

    Returns:
        The path the cache uses for that asset, whether or not it exists.

    Raises:
        ValueError: Either id is unsafe, or the path would escape the cache root.
    """
    provider, sep, name = dataset_id.partition(":")
    if not sep or any(
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", part) for part in (provider, name)
    ):
        raise ValueError(f"unsafe dataset id: {dataset_id!r}")
    safe_id = asset_id.replace("/", "_")
    if not safe_id or safe_id in {".", ".."} or "\\" in safe_id or "\x00" in safe_id:
        raise ValueError(f"unsafe asset id: {asset_id!r}")
    base = (root or cache_dir()).expanduser().resolve()
    path = base / provider / name / safe_id
    for candidate in (path, path.with_name(path.name + ".provenance.json")):
        if not candidate.resolve().is_relative_to(base):
            raise ValueError(f"cache path escapes root: {candidate}")
    return path


def sha256_file(path: Path) -> str:
    """Hex sha256 of a file, prefixed 'sha256:' to match Asset.checksum."""
    with path.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256")
    return f"sha256:{digest.hexdigest()}"
