"""A read-only mirror of pinned bytes, addressed by checksum.

An object lives at ``<mirror>/sha256/<hex>`` and nowhere else, so the lockfile
entry's checksum is the whole lookup and no schema changes. Restore consults
the mirror only after the pinned URL fails to reproduce its pin, and only when
``USDATA_MIRROR_URL`` names one; the SDK never uploads. See ADR 0030.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx

from usdata.cache import sha256_file
from usdata.protocols import http

ENV_VAR = "USDATA_MIRROR_URL"
PREFIX = "sha256/"


class MirrorMismatch(RuntimeError):
    """The mirror served bytes whose checksum is not the one their key names."""


def mirror_url() -> str | None:
    """The configured mirror base URL without a trailing slash, or ``None`` when unset."""
    value = os.environ.get(ENV_VAR, "").strip().rstrip("/")
    return value or None


def object_key(checksum: str) -> str:
    """The mirror key for a pinned checksum: ``sha256/<hex>``."""
    algorithm, sep, digest = checksum.partition(":")
    if not sep or algorithm != "sha256" or len(digest) != 64 or not digest.isalnum():
        raise ValueError(f"not a sha256 checksum: {checksum!r}")
    return PREFIX + digest.lower()


def object_url(base: str, checksum: str) -> str:
    """The public URL of one pinned object on a mirror."""
    return f"{base.rstrip('/')}/{object_key(checksum)}"


def download(base: str, checksum: str, dest: Path, client: httpx.Client) -> str:
    """Fetch the object a checksum names into ``dest`` and prove it is that object.

    Returns:
        The URL the bytes came from.

    Raises:
        httpx.HTTPStatusError: The mirror holds no such object, or refused it.
        MirrorMismatch: The mirror answered with bytes of another checksum.
    """
    url = object_url(base, checksum)
    http.download(url, dest, client)
    if (found := sha256_file(dest)) != checksum:
        raise MirrorMismatch(f"{url} holds {found}, not the {checksum} it is named for")
    return url
