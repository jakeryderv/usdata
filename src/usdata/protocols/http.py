"""Shared HTTP client configuration and streaming download."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from usdata import __version__
from usdata._files import staged_path

USER_AGENT = f"usdata/{__version__} (+https://github.com/jakeryderv/usdata)"
DEFAULT_TIMEOUT = httpx.Timeout(10.0, read=120.0)


def client(**kwargs: Any) -> httpx.Client:
    """A configured client. Callers own its lifetime; use as a context manager."""
    kwargs.setdefault("headers", {"User-Agent": USER_AGENT})
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    kwargs.setdefault("follow_redirects", True)
    return httpx.Client(**kwargs)


def download(url: str, dest: Path, http: httpx.Client | None = None) -> Path:
    """Stream ``url`` to ``dest`` atomically. Raises ``httpx.HTTPStatusError`` on 4xx/5xx."""
    own = http is None
    http = http or client()
    try:
        with staged_path(dest) as tmp, http.stream("GET", url) as resp:
            resp.raise_for_status()
            with tmp.open("wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
    finally:
        if own:
            http.close()
    return dest
