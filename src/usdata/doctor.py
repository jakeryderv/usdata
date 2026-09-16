"""Read-only environment report: interpreter, reader extras, cache, and endpoints.

``diagnose`` only observes. It imports optional modules, reads environment
variables, stats the cache directory, and - when asked - makes one bounded
request per upstream host family. It never creates, moves, or repairs anything;
the CLI prints what it finds and leaves the fixing to the reader.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from collections import Counter
from collections.abc import Iterator
from enum import StrEnum
from importlib import import_module
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version
from pathlib import Path
from time import monotonic
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

from usdata import __version__
from usdata._grib import LIBRARY_HINT
from usdata.cache import ENV_VAR, cache_dir
from usdata.models import READER_EXTRAS
from usdata.protocols import http
from usdata.registry import default_registry

READER_MODULES: dict[str, tuple[str, ...]] = {
    "pandas": ("pandas",),
    "radar": ("xradar",),
    "netcdf": ("xarray", "h5netcdf"),
    "grib": ("eccodes", "xarray", "numpy"),
}
ENV_VARS = (ENV_VAR, "XDG_CACHE_HOME")
PROBE_TIMEOUT = 5.0
MAX_PROBES = 8
GIB = 1024**3


class CheckStatus(StrEnum):
    """Outcome of one check: usable, usable but worth knowing, or broken."""

    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


class Check(BaseModel):
    """One observation, named so it can be grepped and compared across machines."""

    name: str
    status: CheckStatus
    detail: str


class Report(BaseModel):
    """Every check one ``diagnose`` call made, in the order it made them."""

    checks: list[Check]

    @property
    def failed(self) -> bool:
        """True when any check is ``fail``; the CLI exits 1 on that."""
        return any(check.status is CheckStatus.FAIL for check in self.checks)


def diagnose(*, network: bool = False) -> Report:
    """Report the interpreter, reader extras, cache, and environment variables.

    Args:
        network: Also probe one upstream host per distinct family used by the
            available datasets, with a short timeout and one request each.
            Left false, nothing here touches the network.

    Returns:
        A ``Report`` whose checks are ordered interpreter, package, extras,
        cache, environment, endpoints. A missing optional extra is ``warn``;
        a cache directory that cannot be written is ``fail``.
    """
    checks = [*_runtime_checks(), *_reader_checks(), *_cache_checks(), *_environment_checks()]
    if network:
        checks.extend(_endpoint_checks())
    return Report(checks=checks)


def probe_hosts() -> list[str]:
    """Hosts to probe: the homepage hosts of available datasets, most used first."""
    counts: Counter[str] = Counter()
    for dataset in default_registry().list(status="available"):
        host = urlparse(dataset.homepage).hostname if dataset.homepage else None
        if host:
            counts[host] += 1
    return sorted(counts, key=lambda host: (-counts[host], host))[:MAX_PROBES]


def _runtime_checks() -> Iterator[Check]:
    """The interpreter, the machine, and where this usdata is installed."""
    interpreter = f"{platform.python_version()} ({platform.python_implementation()})"
    yield Check(name="python", status=CheckStatus.OK, detail=f"{interpreter} at {sys.executable}")
    yield Check(
        name="platform",
        status=CheckStatus.OK,
        detail=f"{platform.platform()} on {platform.machine() or 'unknown machine'}",
    )
    yield Check(
        name="usdata",
        status=CheckStatus.OK,
        detail=f"{__version__} from {Path(__file__).resolve().parent}",
    )


def _module_version(name: str) -> str:
    try:
        return distribution_version(name)
    except PackageNotFoundError:
        return "unknown version"


def _reader_checks() -> Iterator[Check]:
    """One check per reader extra, warning rather than failing when one is absent."""
    for extra in READER_EXTRAS:
        yield _reader_check(extra)


def _reader_check(extra: str) -> Check:
    """Import an extra's modules, then for grib ask ecCodes for its library version."""
    name = f"extra:{extra}"
    modules: list[Any] = []
    for module in READER_MODULES[extra]:
        try:
            modules.append(import_module(module))
        except (ImportError, RuntimeError, OSError) as error:
            # eccodes imports and then fails to load its shared library.
            return Check(
                name=name,
                status=CheckStatus.WARN,
                detail=f'not usable ({error}); install: pip install "usdata[{extra}]"',
            )
    detail = ", ".join(f"{module} {_module_version(module)}" for module in READER_MODULES[extra])
    if extra != "grib":
        return Check(name=name, status=CheckStatus.OK, detail=detail)
    try:
        library = modules[0].codes_get_api_version()
    except (AttributeError, RuntimeError, OSError) as error:
        return Check(
            name=name, status=CheckStatus.WARN, detail=f"{detail}; {LIBRARY_HINT} ({error})"
        )
    return Check(name=name, status=CheckStatus.OK, detail=f"{detail}, ecCodes library {library}")


def _nearest_existing(path: Path) -> Path:
    """The deepest existing ancestor of a path, or the path itself when it exists."""
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def _free_space(path: Path) -> str:
    try:
        return f"{shutil.disk_usage(path).free / GIB:.1f} GiB free"
    except OSError as error:
        return f"free space unknown ({error})"


def _cache_checks() -> Iterator[Check]:
    """Where the cache is, whether it can be written, and how much room is left."""
    root = cache_dir()
    anchor = _nearest_existing(root)
    space = _free_space(anchor)
    if root.exists() and not root.is_dir():
        yield Check(name="cache", status=CheckStatus.FAIL, detail=f"{root}: not a directory")
        return
    state = "exists" if root.exists() else f"not created yet, nearest parent {anchor}"
    if not os.access(anchor, os.W_OK | os.X_OK):
        yield Check(
            name="cache",
            status=CheckStatus.FAIL,
            detail=f"{root}: {state}, not writable, {space}",
        )
        return
    yield Check(name="cache", status=CheckStatus.OK, detail=f"{root}: {state}, writable, {space}")


def _environment_checks() -> Iterator[Check]:
    """The environment variables that move the cache, reported only when set."""
    for name in ENV_VARS:
        value = os.environ.get(name)
        if value:
            yield Check(name=f"env:{name}", status=CheckStatus.OK, detail=value)


def _endpoint_checks() -> Iterator[Check]:
    """One bounded request per upstream host; an unreachable host is a failure."""
    hosts = probe_hosts()
    if not hosts:
        return
    with http.client(timeout=httpx.Timeout(PROBE_TIMEOUT)) as client:
        for host in hosts:
            yield _probe(host, client)


def _probe(host: str, client: httpx.Client) -> Check:
    """HEAD the host's root, falling back to GET where HEAD is not allowed."""
    url = f"https://{host}/"
    started = monotonic()
    try:
        response = client.head(url)
        if response.status_code in {403, 405, 501}:
            response = client.get(url)
    except httpx.HTTPError as error:
        return Check(
            name=f"host:{host}",
            status=CheckStatus.FAIL,
            detail=f"unreachable: {type(error).__name__}: {error}",
        )
    elapsed = int((monotonic() - started) * 1000)
    return Check(
        name=f"host:{host}",
        status=CheckStatus.OK,
        detail=f"reachable: HTTP {response.status_code} in {elapsed} ms",
    )
